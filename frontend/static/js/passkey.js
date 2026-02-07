class PasskeyManager {
    constructor(api) {
        this.api = api;
    }

    /**
     * Check if WebAuthn is supported in this browser
     */
    isSupported() {
        return window.PublicKeyCredential !== undefined &&
               navigator.credentials !== undefined;
    }

    /**
     * Convert base64url to ArrayBuffer
     */
    base64urlToBuffer(base64url) {
        const base64 = base64url.replace(/-/g, '+').replace(/_/g, '/');
        const padLen = (4 - (base64.length % 4)) % 4;
        const padded = base64 + '='.repeat(padLen);
        const binary = atob(padded);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i);
        }
        return bytes.buffer;
    }

    /**
     * Convert ArrayBuffer to base64url
     */
    bufferToBase64url(buffer) {
        const bytes = new Uint8Array(buffer);
        let binary = '';
        for (let i = 0; i < bytes.length; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        const base64 = btoa(binary);
        return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
    }

    /**
     * Register a new passkey
     */
    async register(credentialName = null) {
        if (!this.isSupported()) {
            throw new Error('Passkeys er ikke støttet i denne nettleseren');
        }

        try {
            // Start registration
            const beginResponse = await this.api.request('/auth/passkey/register/begin', {
                method: 'POST',
                body: JSON.stringify({ credential_name: credentialName })
            });

            // Convert challenge and user.id to ArrayBuffer
            const publicKey = {
                ...beginResponse,
                challenge: this.base64urlToBuffer(beginResponse.challenge),
                user: {
                    ...beginResponse.user,
                    id: this.base64urlToBuffer(beginResponse.user.id)
                },
                excludeCredentials: beginResponse.excludeCredentials?.map(cred => ({
                    ...cred,
                    id: this.base64urlToBuffer(cred.id)
                }))
            };

            // Create credential
            const credential = await navigator.credentials.create({ publicKey });

            if (!credential) {
                throw new Error('Kunne ikke opprette passkey');
            }

            // Complete registration
            const attestation = {
                id: credential.id,
                rawId: this.bufferToBase64url(credential.rawId),
                type: credential.type,
                response: {
                    clientDataJSON: this.bufferToBase64url(credential.response.clientDataJSON),
                    attestationObject: this.bufferToBase64url(credential.response.attestationObject)
                },
                challenge_key: beginResponse.challenge_key
            };

            const completeResponse = await this.api.request('/auth/passkey/register/complete', {
                method: 'POST',
                body: JSON.stringify({
                    credential_name: credentialName,
                    attestation: attestation
                })
            });

            return completeResponse;

        } catch (error) {
            console.error('Passkey registration error:', error);
            throw error;
        }
    }

    /**
     * Login with passkey
     */
    async login(email = null) {
        if (!this.isSupported()) {
            throw new Error('Passkeys er ikke støttet i denne nettleseren');
        }

        try {
            // Start login
            const beginResponse = await this.api.request('/auth/passkey/login/begin', {
                method: 'POST',
                body: JSON.stringify({ email: email })
            });

            // Convert challenge to ArrayBuffer
            const publicKey = {
                ...beginResponse,
                challenge: this.base64urlToBuffer(beginResponse.challenge),
                allowCredentials: beginResponse.allowCredentials?.map(cred => ({
                    ...cred,
                    id: this.base64urlToBuffer(cred.id)
                }))
            };

            // Get credential
            const credential = await navigator.credentials.get({ publicKey });

            if (!credential) {
                throw new Error('Kunne ikke autentisere med passkey');
            }

            // Complete login
            const assertion = {
                id: credential.id,
                rawId: this.bufferToBase64url(credential.rawId),
                type: credential.type,
                response: {
                    clientDataJSON: this.bufferToBase64url(credential.response.clientDataJSON),
                    authenticatorData: this.bufferToBase64url(credential.response.authenticatorData),
                    signature: this.bufferToBase64url(credential.response.signature),
                    userHandle: credential.response.userHandle ?
                        this.bufferToBase64url(credential.response.userHandle) : null
                },
                challenge_key: beginResponse.challenge_key
            };

            const completeResponse = await this.api.request('/auth/passkey/login/complete', {
                method: 'POST',
                body: JSON.stringify({
                    credential_id: credential.id,
                    assertion: assertion
                })
            });

            return completeResponse;

        } catch (error) {
            console.error('Passkey login error:', error);
            throw error;
        }
    }

    /**
     * List user's passkeys
     */
    async list() {
        return await this.api.request('/auth/passkey/credentials');
    }

    /**
     * Delete a passkey
     */
    async delete(credentialId) {
        return await this.api.request(`/auth/passkey/credentials/${credentialId}`, {
            method: 'DELETE'
        });
    }

    /**
     * Rename a passkey
     */
    async rename(credentialId, newName) {
        return await this.api.request(`/auth/passkey/credentials/${credentialId}/rename?new_name=${encodeURIComponent(newName)}`, {
            method: 'PATCH'
        });
    }
}

// Export for use in other modules
window.PasskeyManager = PasskeyManager;
