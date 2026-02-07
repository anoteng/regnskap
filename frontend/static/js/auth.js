import api from './api.js';

class Auth {
    constructor() {
        this.currentUser = null;
        this.passkeyManager = null;
    }

    async initPasskeyManager() {
        if (!this.passkeyManager && window.PasskeyManager) {
            this.passkeyManager = new window.PasskeyManager(api);
        }
        return this.passkeyManager;
    }

    isAuthenticated() {
        return !!api.token;
    }

    async login(email, password) {
        try {
            await api.login(email, password);
            return true;
        } catch (error) {
            throw error;
        }
    }

    async register(fullName, email, password) {
        try {
            await api.register(fullName, email, password);
            await api.login(email, password);
            return true;
        } catch (error) {
            throw error;
        }
    }

    logout() {
        api.clearToken();
        this.currentUser = null;
    }

    async setupAuthUI() {
        const loginForm = document.getElementById('loginForm');
        const registerForm = document.getElementById('registerForm');
        const showRegister = document.getElementById('show-register');
        const showLogin = document.getElementById('show-login');

        // Initialize passkey manager and show passkey login if supported
        await this.initPasskeyManager();
        if (this.passkeyManager && this.passkeyManager.isSupported()) {
            document.getElementById('passkey-login-section').style.display = 'block';

            document.getElementById('passkey-login-btn').addEventListener('click', async () => {
                try {
                    const email = document.getElementById('login-email').value;
                    const result = await this.passkeyManager.login(email || null);
                    api.setToken(result.access_token);
                    window.location.reload();
                } catch (error) {
                    console.error('Passkey login error:', error);
                    alert('Passkey-innlogging feilet: ' + error.message);
                }
            });
        }

        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('login-email').value;
            const password = document.getElementById('login-password').value;

            try {
                await this.login(email, password);
                window.location.reload();
            } catch (error) {
                alert('Login feilet: ' + error.message);
            }
        });

        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const name = document.getElementById('register-name').value;
            const email = document.getElementById('register-email').value;
            const password = document.getElementById('register-password').value;

            try {
                await this.register(name, email, password);
                window.location.reload();
            } catch (error) {
                alert('Registrering feilet: ' + error.message);
            }
        });

        showRegister.addEventListener('click', (e) => {
            e.preventDefault();
            document.getElementById('login-form').style.display = 'none';
            document.getElementById('register-form').style.display = 'block';
        });

        showLogin.addEventListener('click', (e) => {
            e.preventDefault();
            document.getElementById('register-form').style.display = 'none';
            document.getElementById('reset-password-form').style.display = 'none';
            document.getElementById('login-form').style.display = 'block';
        });

        // Forgot password link
        document.getElementById('forgot-password').addEventListener('click', (e) => {
            e.preventDefault();
            document.getElementById('login-form').style.display = 'none';
            document.getElementById('reset-password-form').style.display = 'block';
        });

        // Back to login from reset
        document.getElementById('back-to-login').addEventListener('click', (e) => {
            e.preventDefault();
            document.getElementById('reset-password-form').style.display = 'none';
            document.getElementById('login-form').style.display = 'block';
        });

        // Password reset form
        document.getElementById('resetPasswordForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('reset-email').value;

            try {
                const response = await fetch('/api/auth/password-reset/request', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email })
                });

                const data = await response.json();

                if (response.ok) {
                    document.getElementById('reset-instructions').innerHTML =
                        `<strong style="color: green;">✓ ${data.message}</strong>` +
                        (data.has_passkey ? '<br><br><em>Tips: Du har en passkey registrert, og kan også bruke den for å tilbakestille passordet!</em>' : '');
                } else {
                    alert('Feil: ' + (data.detail || 'Kunne ikke sende tilbakestillingslenke'));
                }
            } catch (error) {
                alert('Feil ved tilbakestilling: ' + error.message);
            }
        });

        document.getElementById('logout-btn').addEventListener('click', () => {
            this.logout();
            window.location.reload();
        });
    }
}

export default new Auth();
