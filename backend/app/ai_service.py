"""
AI Service for receipt analysis and posting suggestions
Supports multiple providers: OpenAI, Anthropic (Claude)
"""

import base64
import json
from typing import Dict, Any, Optional, Tuple
from decimal import Decimal
from datetime import datetime, date
from sqlalchemy.orm import Session
import httpx

from .models import AIConfig, AIUsage, User, Ledger, Receipt, Account, UserSubscription, SubscriptionStatus, UserMonthlyUsage


class AIService:
    """Main AI service with provider abstraction"""

    def __init__(self, db: Session):
        self.db = db
        self.config = self._get_active_config()

    def _get_active_config(self) -> Optional[AIConfig]:
        """Get the active AI configuration"""
        return self.db.query(AIConfig).filter(
            AIConfig.is_active == True
        ).first()

    def check_ai_access(self, user: User) -> Tuple[bool, Optional[str]]:
        """
        Check if user has access to AI features
        Returns: (has_access: bool, error_message: Optional[str])
        """
        # Check if user's AI access is blocked by admin
        if not user.ai_access_enabled:
            reason = user.ai_access_blocked_reason or "AI-tilgang er deaktivert av administrator"
            return False, reason

        # Get user's active subscription
        subscription = self.db.query(UserSubscription).filter(
            UserSubscription.user_id == user.id,
            UserSubscription.status == SubscriptionStatus.ACTIVE
        ).first()

        if not subscription:
            return False, "Du må ha et aktivt abonnement for å bruke AI-funksjoner"

        # Check if plan includes AI
        plan = subscription.plan
        if not plan.ai_enabled:
            return False, f"AI-funksjoner er ikke inkludert i {plan.name}-abonnementet. Oppgrader til AI-abonnementet for å bruke disse funksjonene."

        # Check monthly AI operation limit
        if plan.max_ai_operations_per_month is not None:
            now = datetime.utcnow()
            current_year = now.year
            current_month = now.month

            # Get monthly usage
            usage = self.db.query(UserMonthlyUsage).filter(
                UserMonthlyUsage.user_id == user.id,
                UserMonthlyUsage.year == current_year,
                UserMonthlyUsage.month == current_month
            ).first()

            ai_ops_count = usage.ai_operations_count if usage else 0

            if ai_ops_count >= plan.max_ai_operations_per_month:
                return False, f"Du har nådd månedens grense på {plan.max_ai_operations_per_month} AI-operasjoner for {plan.name}-abonnementet. Oppgrader for ubegrensede AI-operasjoner."

        return True, None

    def increment_ai_operations(self, user: User):
        """Increment user's monthly AI operations counter"""
        now = datetime.utcnow()
        current_year = now.year
        current_month = now.month

        # Get or create monthly usage record
        usage = self.db.query(UserMonthlyUsage).filter(
            UserMonthlyUsage.user_id == user.id,
            UserMonthlyUsage.year == current_year,
            UserMonthlyUsage.month == current_month
        ).first()

        if usage:
            usage.ai_operations_count += 1
        else:
            usage = UserMonthlyUsage(
                user_id=user.id,
                year=current_year,
                month=current_month,
                upload_count=0,
                ai_operations_count=1
            )
            self.db.add(usage)

        self.db.commit()

    async def analyze_receipt(
        self,
        receipt: Receipt,
        user: User,
        ledger: Ledger
    ) -> Dict[str, Any]:
        """
        Analyze a receipt image and extract structured data
        Returns: dict with extracted data (date, amount, vendor, description, suggested_account)
        """
        # Check AI access
        has_access, error_msg = self.check_ai_access(user)
        if not has_access:
            raise ValueError(error_msg)

        if not self.config:
            raise ValueError("No active AI configuration found")

        # Read image file
        with open(receipt.image_path, 'rb') as f:
            image_data = f.read()

        # Get list of available accounts for this ledger
        accounts = self._get_ledger_accounts(ledger)

        # Build prompt
        prompt = self._build_receipt_analysis_prompt(accounts)

        # Call AI provider
        if self.config.provider == 'openai':
            result = await self._call_openai_vision(image_data, prompt, receipt.mime_type)
        elif self.config.provider == 'anthropic':
            result = await self._call_anthropic_vision(image_data, prompt, receipt.mime_type)
        else:
            raise ValueError(f"Unsupported AI provider: {self.config.provider}")

        # Track usage
        self._track_usage(
            user=user,
            ledger=ledger,
            operation_type='receipt_analysis',
            tokens_used=result['tokens_used'],
            cost_usd=result['cost_usd'],
            request_data={'receipt_id': receipt.id},
            response_data=result['extracted_data']
        )

        # Increment AI operations counter
        self.increment_ai_operations(user)

        return result['extracted_data']

    async def suggest_posting(
        self,
        description: str,
        amount: Decimal,
        transaction_date: date,
        user: User,
        ledger: Ledger,
        vendor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Suggest journal entries for a transaction
        Returns: dict with suggested debit/credit accounts and amounts
        """
        # Check AI access
        has_access, error_msg = self.check_ai_access(user)
        if not has_access:
            raise ValueError(error_msg)

        if not self.config:
            raise ValueError("No active AI configuration found")

        # Get list of available accounts
        accounts = self._get_ledger_accounts(ledger)

        # Build prompt
        prompt = self._build_posting_suggestion_prompt(
            description, amount, transaction_date, vendor, accounts
        )

        # Call AI provider
        if self.config.provider == 'openai':
            result = await self._call_openai_text(prompt)
        elif self.config.provider == 'anthropic':
            result = await self._call_anthropic_text(prompt)
        else:
            raise ValueError(f"Unsupported AI provider: {self.config.provider}")

        # Track usage
        self._track_usage(
            user=user,
            ledger=ledger,
            operation_type='posting_suggestion',
            tokens_used=result['tokens_used'],
            cost_usd=result['cost_usd'],
            request_data={
                'description': description,
                'amount': str(amount),
                'date': str(transaction_date)
            },
            response_data=result['suggestion']
        )

        # Increment AI operations counter
        self.increment_ai_operations(user)

        return result['suggestion']

    def _get_ledger_accounts(self, ledger: Ledger) -> list:
        """Get formatted list of accounts for the ledger"""
        from .models import LedgerAccountSettings

        # Get active accounts
        query = self.db.query(Account).filter(Account.is_active == True)

        # Filter out hidden accounts for this ledger
        hidden_settings = self.db.query(LedgerAccountSettings).filter(
            LedgerAccountSettings.ledger_id == ledger.id,
            LedgerAccountSettings.is_hidden == True
        ).all()
        hidden_ids = [s.account_id for s in hidden_settings]

        if hidden_ids:
            query = query.filter(~Account.id.in_(hidden_ids))

        accounts = query.all()

        return [
            {
                'number': acc.account_number,
                'name': acc.account_name,
                'type': acc.account_type.value
            }
            for acc in accounts
        ]

    def _build_receipt_analysis_prompt(self, accounts: list) -> str:
        """Build prompt for receipt analysis"""
        account_list = "\n".join([
            f"{acc['number']}: {acc['name']} ({acc['type']})"
            for acc in accounts[:50]  # Limit to avoid token overflow
        ])

        return f"""Analyser denne kvitteringen og ekstraher følgende informasjon i JSON-format:

{{
  "date": "YYYY-MM-DD",
  "amount": 123.45,
  "vendor": "Butikknavn",
  "description": "Kort beskrivelse av kjøpet",
  "suggested_account": "kontonummer",
  "confidence": 0.95
}}

Tilgjengelige kontoer:
{account_list}

Regler:
- date: Kvitteringsdato
- amount: Totalbeløp inkludert MVA
- vendor: Butikk/leverandør
- description: Kort beskrivelse (maks 100 tegn)
- suggested_account: Mest sannsynlige utgiftskonto basert på kjøpet
- confidence: Din sikkerhet (0-1)

Returner BARE JSON, ingen annen tekst."""

    def _build_posting_suggestion_prompt(
        self,
        description: str,
        amount: Decimal,
        transaction_date: date,
        vendor: Optional[str],
        accounts: list
    ) -> str:
        """Build prompt for posting suggestion"""
        account_list = "\n".join([
            f"{acc['number']}: {acc['name']} ({acc['type']})"
            for acc in accounts[:50]
        ])

        vendor_info = f"\nLeverandør: {vendor}" if vendor else ""

        return f"""Foreslå bokføring for denne transaksjonen i JSON-format:

Transaksjon:
- Dato: {transaction_date}
- Beløp: {amount} kr
- Beskrivelse: {description}{vendor_info}

Tilgjengelige kontoer:
{account_list}

Returner forslag i dette formatet:
{{
  "entries": [
    {{"account": "kontonummer", "debit": 123.45, "credit": 0, "description": "..."}},
    {{"account": "kontonummer", "debit": 0, "credit": 123.45, "description": "..."}}
  ],
  "explanation": "Kort forklaring på posteringen",
  "confidence": 0.95
}}

Regler for dobbelt bokføring:
- Sum av debet må være lik sum av kredit
- Utgifter: debiteres utgiftskonto, krediteres bankkonto
- Inntekter: debiteres bankkonto, krediteres inntektskonto
- confidence: Din sikkerhet (0-1)

Returner BARE JSON, ingen annen tekst."""

    async def _call_openai_vision(
        self,
        image_data: bytes,
        prompt: str,
        mime_type: str
    ) -> Dict[str, Any]:
        """Call OpenAI Vision API"""
        # Encode image to base64
        base64_image = base64.b64encode(image_data).decode('utf-8')

        # Prepare request
        headers = {
            'Authorization': f'Bearer {self.config.api_key}',
            'Content-Type': 'application/json'
        }

        payload = {
            'model': self.config.model,
            'messages': [
                {
                    'role': 'user',
                    'content': [
                        {'type': 'text', 'text': prompt},
                        {
                            'type': 'image_url',
                            'image_url': {
                                'url': f'data:{mime_type};base64,{base64_image}'
                            }
                        }
                    ]
                }
            ],
            'max_tokens': self.config.max_tokens,
            'temperature': float(self.config.temperature)
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                'https://api.openai.com/v1/chat/completions',
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()

        # Extract result
        content = data['choices'][0]['message']['content']
        tokens_used = data['usage']['total_tokens']

        # Parse JSON response
        extracted_data = self._extract_json_from_response(content)

        # Estimate cost (example pricing for GPT-4o)
        cost_usd = tokens_used * 0.00001  # Rough estimate

        return {
            'extracted_data': extracted_data,
            'tokens_used': tokens_used,
            'cost_usd': cost_usd
        }

    def _extract_json_from_response(self, content: str) -> dict:
        """Extract JSON from AI response, handling markdown code blocks"""
        # Remove markdown code blocks if present
        content = content.strip()

        # Check for ```json ... ``` format
        if content.startswith('```'):
            # Find the content between ``` markers
            lines = content.split('\n')
            if lines[0].startswith('```'):
                lines = lines[1:]  # Remove first ```json line
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]  # Remove last ``` line
            content = '\n'.join(lines)

        # Try to parse the JSON
        try:
            return json.loads(content.strip())
        except json.JSONDecodeError as e:
            # If parsing fails, try to find JSON object in the text
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            raise ValueError(f"Could not parse JSON from AI response: {str(e)}\nResponse: {content[:200]}")

    async def _call_openai_text(self, prompt: str) -> Dict[str, Any]:
        """Call OpenAI text completion API"""
        headers = {
            'Authorization': f'Bearer {self.config.api_key}',
            'Content-Type': 'application/json'
        }

        payload = {
            'model': self.config.model,
            'messages': [
                {'role': 'user', 'content': prompt}
            ],
            'max_tokens': self.config.max_tokens,
            'temperature': float(self.config.temperature)
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                'https://api.openai.com/v1/chat/completions',
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()

        content = data['choices'][0]['message']['content']
        tokens_used = data['usage']['total_tokens']

        suggestion = self._extract_json_from_response(content)
        cost_usd = tokens_used * 0.00001

        return {
            'suggestion': suggestion,
            'tokens_used': tokens_used,
            'cost_usd': cost_usd
        }

    async def _call_anthropic_vision(
        self,
        image_data: bytes,
        prompt: str,
        mime_type: str
    ) -> Dict[str, Any]:
        """Call Anthropic Claude Vision API"""
        # Encode image to base64
        base64_image = base64.b64encode(image_data).decode('utf-8')

        # Map mime type to Anthropic format
        media_type = mime_type if mime_type in ['image/jpeg', 'image/png', 'image/gif', 'image/webp'] else 'image/jpeg'

        headers = {
            'x-api-key': self.config.api_key,
            'anthropic-version': '2023-06-01',
            'Content-Type': 'application/json'
        }

        payload = {
            'model': self.config.model,
            'max_tokens': self.config.max_tokens,
            'temperature': float(self.config.temperature),
            'messages': [
                {
                    'role': 'user',
                    'content': [
                        {
                            'type': 'image',
                            'source': {
                                'type': 'base64',
                                'media_type': media_type,
                                'data': base64_image
                            }
                        },
                        {
                            'type': 'text',
                            'text': prompt
                        }
                    ]
                }
            ]
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                'https://api.anthropic.com/v1/messages',
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()

        content = data['content'][0]['text']
        input_tokens = data['usage']['input_tokens']
        output_tokens = data['usage']['output_tokens']
        tokens_used = input_tokens + output_tokens

        extracted_data = self._extract_json_from_response(content)

        # Estimate cost (example pricing for Claude 3.5 Sonnet)
        cost_usd = (input_tokens * 0.000003) + (output_tokens * 0.000015)

        return {
            'extracted_data': extracted_data,
            'tokens_used': tokens_used,
            'cost_usd': cost_usd
        }

    async def _call_anthropic_text(self, prompt: str) -> Dict[str, Any]:
        """Call Anthropic Claude text API"""
        headers = {
            'x-api-key': self.config.api_key,
            'anthropic-version': '2023-06-01',
            'Content-Type': 'application/json'
        }

        payload = {
            'model': self.config.model,
            'max_tokens': self.config.max_tokens,
            'temperature': float(self.config.temperature),
            'messages': [
                {'role': 'user', 'content': prompt}
            ]
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                'https://api.anthropic.com/v1/messages',
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()

        content = data['content'][0]['text']
        input_tokens = data['usage']['input_tokens']
        output_tokens = data['usage']['output_tokens']
        tokens_used = input_tokens + output_tokens

        suggestion = self._extract_json_from_response(content)
        cost_usd = (input_tokens * 0.000003) + (output_tokens * 0.000015)

        return {
            'suggestion': suggestion,
            'tokens_used': tokens_used,
            'cost_usd': cost_usd
        }

    def _track_usage(
        self,
        user: User,
        ledger: Ledger,
        operation_type: str,
        tokens_used: int,
        cost_usd: float,
        request_data: Dict,
        response_data: Dict
    ):
        """Track AI usage in database"""
        usage = AIUsage(
            user_id=user.id,
            ledger_id=ledger.id,
            provider=self.config.provider,
            model=self.config.model,
            operation_type=operation_type,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
            request_data=json.dumps(request_data),
            response_data=json.dumps(response_data)
        )
        self.db.add(usage)
        self.db.commit()

    def get_user_usage_stats(self, user_id: int, start_date: Optional[date] = None) -> Dict[str, Any]:
        """Get AI usage statistics for a user"""
        query = self.db.query(AIUsage).filter(AIUsage.user_id == user_id)

        if start_date:
            query = query.filter(AIUsage.created_at >= start_date)

        usages = query.all()

        total_tokens = sum(u.tokens_used for u in usages)
        total_cost = sum(u.cost_usd or 0 for u in usages)

        by_operation = {}
        for usage in usages:
            if usage.operation_type not in by_operation:
                by_operation[usage.operation_type] = {'count': 0, 'tokens': 0, 'cost': 0}
            by_operation[usage.operation_type]['count'] += 1
            by_operation[usage.operation_type]['tokens'] += usage.tokens_used
            by_operation[usage.operation_type]['cost'] += usage.cost_usd or 0

        return {
            'total_operations': len(usages),
            'total_tokens': total_tokens,
            'total_cost_usd': total_cost,
            'by_operation': by_operation
        }
