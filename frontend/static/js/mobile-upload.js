class MobileApp {
    constructor() {
        this.token = localStorage.getItem('token');
        this.ledger = localStorage.getItem('current_ledger');
        this.baseURL = window.location.origin + '/api';
        this.stream = null;
        this.capturedImage = null;
        this.passkeyManager = null;

        // Camera settings
        this.currentFacingMode = 'environment';
        this.flashEnabled = false;
        this.currentZoom = 1;
        this.videoTrack = null;

        // Image editor state
        this.editorCanvas = null;
        this.editorCtx = null;
        this.currentRotation = 0;
        this.currentImage = null;
        this.cropMode = false;
        this.cropArea = { x: 5, y: 5, width: 90, height: 90 }; // Percentage-based
        this.isDraggingCrop = false;
        this.isResizingCrop = false;
        this.dragStartX = 0;
        this.dragStartY = 0;
        this.resizeHandle = null;

        // PWA install prompt
        this.deferredPrompt = null;
        this.isInstalled = false;

        this.init();
    }

    async init() {
        // Register service worker for PWA
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/sw.js')
                .then(() => console.log('Service Worker registered'))
                .catch(err => console.log('Service Worker registration failed:', err));
        }

        // Initialize passkey manager
        const debugEl = document.getElementById('passkey-debug');
        const debugText = document.getElementById('passkey-debug-text');

        console.log('Checking for PasskeyManager...', window.PasskeyManager);

        if (window.PasskeyManager) {
            console.log('PasskeyManager found, initializing...');
            this.passkeyManager = new window.PasskeyManager(this);

            // Show passkey login if supported
            console.log('Checking if passkeys are supported...');
            const isSupported = this.passkeyManager.isSupported();
            console.log('Passkeys supported:', isSupported);

            if (isSupported) {
                console.log('Showing passkey login button');
                document.getElementById('mobile-passkey-login-btn').style.display = 'block';
                document.getElementById('passkey-or-divider').style.display = 'block';
                if (debugEl) {
                    debugText.textContent = '✓ Passkeys støttes i denne nettleseren';
                    debugEl.style.background = '#d1fae5';
                    debugEl.style.display = 'block';
                }
            } else {
                console.log('Passkeys not supported in this browser');
                if (debugEl) {
                    debugText.textContent = '✗ Passkeys støttes ikke i denne nettleseren';
                    debugEl.style.background = '#fee2e2';
                    debugEl.style.display = 'block';
                }
            }
        } else {
            console.error('PasskeyManager not found! Is passkey.js loaded?');
            if (debugEl) {
                debugText.textContent = '✗ PasskeyManager ikke funnet (passkey.js ikke lastet)';
                debugEl.style.background = '#fee2e2';
                debugEl.style.display = 'block';
            }
        }

        // Check authentication and validate session
        if (!this.token) {
            this.showLoginView();
        } else {
            // Validate token before showing upload view
            const isValid = await this.validateSession();
            if (isValid) {
                this.showUploadView();
            } else {
                this.showLoginView();
            }
        }

        this.setupEventListeners();
        this.setupVisibilityChangeHandler();
        this.setupPWAInstallPrompt();
    }

    async validateSession() {
        if (!this.token) return false;

        try {
            console.log('Validating session...');
            // Try to fetch ledgers - if this fails, token is invalid
            const ledgers = await this.request('/ledgers/');

            // If we have ledgers, session is valid
            if (ledgers && ledgers.length > 0) {
                // Update ledger if not set
                if (!this.ledger) {
                    this.ledger = ledgers[0].id;
                    localStorage.setItem('current_ledger', this.ledger);
                }
                console.log('Session valid');
                return true;
            }

            return false;
        } catch (error) {
            console.log('Session validation failed:', error.message);
            // Token is invalid, clear it
            this.logout();
            return false;
        }
    }

    setupVisibilityChangeHandler() {
        // Check session when app comes back from background
        document.addEventListener('visibilitychange', async () => {
            if (!document.hidden && this.token) {
                console.log('App became visible, validating session...');
                const isValid = await this.validateSession();
                if (!isValid) {
                    this.showError('Din sesjon har utløpt. Vennligst logg inn på nytt.');
                    this.showLoginView();
                }
            }
        });

        // Also check on focus (for desktop)
        window.addEventListener('focus', async () => {
            if (this.token) {
                const isValid = await this.validateSession();
                if (!isValid) {
                    this.showError('Din sesjon har utløpt. Vennligst logg inn på nytt.');
                    this.showLoginView();
                }
            }
        });
    }

    setupPWAInstallPrompt() {
        // Check if app is already installed
        this.isInstalled = this.checkIfInstalled();

        if (this.isInstalled) {
            console.log('App is installed as PWA');
            return;
        }

        console.log('App is running in browser, not installed');

        // Listen for beforeinstallprompt event
        window.addEventListener('beforeinstallprompt', (e) => {
            console.log('beforeinstallprompt event fired');
            // Prevent Chrome 67 and earlier from automatically showing the prompt
            e.preventDefault();
            // Stash the event so it can be triggered later
            this.deferredPrompt = e;
            // Show install banner
            this.showInstallBanner();
        });

        // Listen for app installed event
        window.addEventListener('appinstalled', () => {
            console.log('PWA was installed');
            this.isInstalled = true;
            this.hideInstallBanner();
            this.showSuccess('Appen er nå installert! 🎉');
        });

        // Check if we should show install banner (not on all browsers)
        if (!this.deferredPrompt && !this.isInstalled) {
            // For iOS Safari and other browsers that don't support beforeinstallprompt
            this.showInstallInfo();
        }
    }

    checkIfInstalled() {
        // Check if running as standalone PWA
        if (window.matchMedia('(display-mode: standalone)').matches) {
            return true;
        }

        // Check for iOS Safari standalone
        if (window.navigator.standalone === true) {
            return true;
        }

        // Check if referred from homescreen
        if (document.referrer.includes('android-app://')) {
            return true;
        }

        return false;
    }

    showInstallBanner() {
        // Create install banner
        const banner = document.createElement('div');
        banner.id = 'install-banner';
        banner.style.cssText = `
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1rem;
            box-shadow: 0 -4px 12px rgba(0,0,0,0.3);
            z-index: 9999;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            animation: slideUp 0.3s ease-out;
        `;

        banner.innerHTML = `
            <div style="flex: 1;">
                <strong style="display: block; margin-bottom: 0.25rem;">📱 Installer appen</strong>
                <small style="opacity: 0.9;">Få raskere tilgang og bedre opplevelse</small>
            </div>
            <button id="install-btn" class="btn btn-primary" style="background: white; color: #667eea; font-weight: bold; white-space: nowrap;">
                Installer
            </button>
            <button id="dismiss-install" style="background: none; border: none; color: white; font-size: 1.5rem; padding: 0; width: 30px; height: 30px; cursor: pointer;">
                ×
            </button>
        `;

        // Add slide-up animation
        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideUp {
                from {
                    transform: translateY(100%);
                }
                to {
                    transform: translateY(0);
                }
            }
        `;
        document.head.appendChild(style);

        document.body.appendChild(banner);

        // Install button handler
        document.getElementById('install-btn').addEventListener('click', () => {
            this.triggerInstall();
        });

        // Dismiss button handler
        document.getElementById('dismiss-install').addEventListener('click', () => {
            this.hideInstallBanner();
            // Remember dismissal for this session
            sessionStorage.setItem('install-banner-dismissed', 'true');
        });
    }

    showInstallInfo() {
        // For browsers that don't support programmatic install (iOS Safari)
        const dismissed = sessionStorage.getItem('install-banner-dismissed');
        if (dismissed) return;

        const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
        const isSafari = /Safari/.test(navigator.userAgent) && !/Chrome/.test(navigator.userAgent);

        if (isIOS && isSafari) {
            // Show iOS-specific instructions
            setTimeout(() => {
                const banner = document.createElement('div');
                banner.id = 'install-banner';
                banner.style.cssText = `
                    position: fixed;
                    bottom: 0;
                    left: 0;
                    right: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 1rem;
                    box-shadow: 0 -4px 12px rgba(0,0,0,0.3);
                    z-index: 9999;
                    animation: slideUp 0.3s ease-out;
                `;

                banner.innerHTML = `
                    <div style="margin-bottom: 0.5rem;">
                        <strong style="display: block; margin-bottom: 0.5rem;">📱 Installer appen på iOS</strong>
                        <ol style="margin: 0; padding-left: 1.5rem; font-size: 0.9rem; line-height: 1.6;">
                            <li>Trykk på Del-knappen <span style="font-size: 1.2rem;">⎋</span></li>
                            <li>Velg "Legg til på Hjem-skjerm"</li>
                            <li>Trykk "Legg til"</li>
                        </ol>
                    </div>
                    <button id="dismiss-install" class="btn btn-secondary btn-large" style="width: 100%; background: rgba(255,255,255,0.2);">
                        Lukk
                    </button>
                `;

                document.body.appendChild(banner);

                document.getElementById('dismiss-install').addEventListener('click', () => {
                    this.hideInstallBanner();
                    sessionStorage.setItem('install-banner-dismissed', 'true');
                });
            }, 2000); // Show after 2 seconds
        }
    }

    async triggerInstall() {
        if (!this.deferredPrompt) {
            console.log('No install prompt available');
            return;
        }

        // Show the install prompt
        this.deferredPrompt.prompt();

        // Wait for the user to respond to the prompt
        const { outcome } = await this.deferredPrompt.userChoice;
        console.log(`User response to install prompt: ${outcome}`);

        if (outcome === 'accepted') {
            console.log('User accepted the install prompt');
            this.hideInstallBanner();
        } else {
            console.log('User dismissed the install prompt');
        }

        // Clear the deferredPrompt
        this.deferredPrompt = null;
    }

    hideInstallBanner() {
        const banner = document.getElementById('install-banner');
        if (banner) {
            banner.style.animation = 'slideDown 0.3s ease-out';
            setTimeout(() => banner.remove(), 300);
        }

        // Add slide-down animation
        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideDown {
                from {
                    transform: translateY(0);
                }
                to {
                    transform: translateY(100%);
                }
            }
        `;
        document.head.appendChild(style);
    }

    // API compatibility method for PasskeyManager
    async request(url, options = {}) {
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };

        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }

        if (this.ledger) {
            headers['X-Ledger-ID'] = this.ledger;
        }

        const response = await fetch(this.baseURL + url, {
            ...options,
            headers
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Request failed' }));
            throw new Error(error.detail || 'Request failed');
        }

        return await response.json();
    }

    setToken(token) {
        this.token = token;
        localStorage.setItem('token', token);
    }

    setupEventListeners() {
        // Passkey login
        document.getElementById('mobile-passkey-login-btn')?.addEventListener('click', async () => {
            try {
                const email = document.getElementById('login-email').value;
                const result = await this.passkeyManager.login(email || null);
                this.setToken(result.access_token);

                // Get user's ledgers
                const ledgers = await this.request('/ledgers/');
                if (ledgers.length > 0) {
                    this.ledger = ledgers[0].id;
                    localStorage.setItem('current_ledger', this.ledger);
                }

                this.showSuccess('Logget inn!');
                this.showUploadView();
            } catch (error) {
                console.error('Passkey login error:', error);
                this.showError('Kunne ikke logge inn med passkey: ' + error.message);
            }
        });

        // Login form
        document.getElementById('mobile-login-form')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.login();
        });

        // Camera buttons
        document.getElementById('start-camera-btn')?.addEventListener('click', () => this.startCamera());
        document.getElementById('take-photo-btn')?.addEventListener('click', () => this.takePhoto());

        // Camera controls
        document.getElementById('flash-btn')?.addEventListener('click', () => this.toggleFlash());
        document.getElementById('switch-camera-btn')?.addEventListener('click', () => this.switchCamera());

        // Zoom control
        document.getElementById('zoom-slider')?.addEventListener('input', (e) => this.setZoom(e.target.value));

        // File input
        document.getElementById('file-input')?.addEventListener('change', (e) => this.handleFileSelect(e));

        // Upload form
        document.getElementById('upload-form')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.uploadReceipt();
        });

        // Logout
        document.getElementById('logout-btn')?.addEventListener('click', () => this.logout());
    }

    showLoginView() {
        document.getElementById('login-view').style.display = 'block';
        document.getElementById('upload-view').style.display = 'none';
    }

    showUploadView() {
        document.getElementById('login-view').style.display = 'none';
        document.getElementById('upload-view').style.display = 'block';
    }

    async login() {
        const email = document.getElementById('login-email').value;
        const password = document.getElementById('login-password').value;

        try {
            const response = await fetch(`${this.baseURL}/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: new URLSearchParams({
                    username: email,
                    password: password
                })
            });

            if (!response.ok) {
                throw new Error('Innlogging feilet');
            }

            const data = await response.json();
            this.token = data.access_token;
            localStorage.setItem('token', this.token);

            // Get user's ledgers
            const ledgersResponse = await fetch(`${this.baseURL}/ledgers/`, {
                headers: { 'Authorization': `Bearer ${this.token}` }
            });

            const ledgers = await ledgersResponse.json();
            if (ledgers.length > 0) {
                this.ledger = ledgers[0].id;
                localStorage.setItem('current_ledger', this.ledger);
            }

            this.showSuccess('Logget inn!');
            this.showUploadView();
        } catch (error) {
            this.showError('Kunne ikke logge inn: ' + error.message);
        }
    }

    logout() {
        console.log('Logging out...');
        localStorage.removeItem('token');
        localStorage.removeItem('current_ledger');
        this.token = null;
        this.ledger = null;

        // Reset any pending uploads
        this.reset();

        this.showLoginView();
        this.showSuccess('Du er nå logget ut');
    }

    async startCamera() {
        try {
            console.log('Starting camera...');

            // Check if elements exist
            const video = document.getElementById('camera-preview');
            const cameraContainer = document.getElementById('camera-preview-container');
            const startBtn = document.getElementById('start-camera-btn');
            const takeBtn = document.getElementById('take-photo-btn');

            console.log('Elements found:', {
                video: !!video,
                cameraContainer: !!cameraContainer,
                startBtn: !!startBtn,
                takeBtn: !!takeBtn
            });

            if (!video) {
                throw new Error('Video element not found');
            }

            // Advanced camera constraints for better document capture
            const constraints = {
                video: {
                    facingMode: this.currentFacingMode,
                    width: { ideal: 1920 },
                    height: { ideal: 1080 },
                    aspectRatio: { ideal: 16/9 }
                }
            };

            console.log('Requesting camera access...');
            this.stream = await navigator.mediaDevices.getUserMedia(constraints);
            this.videoTrack = this.stream.getVideoTracks()[0];

            console.log('Camera stream obtained');

            // Set video source
            video.srcObject = this.stream;

            // Try to get capabilities (may not be supported on all devices)
            try {
                const capabilities = this.videoTrack.getCapabilities();
                console.log('Camera capabilities:', capabilities);

                // Enable zoom control if supported
                const zoomControl = document.getElementById('zoom-control');
                const zoomSlider = document.getElementById('zoom-slider');
                if (capabilities.zoom && zoomControl && zoomSlider) {
                    console.log('Zoom supported');
                    zoomControl.style.display = 'block';
                    zoomSlider.min = capabilities.zoom.min || 1;
                    zoomSlider.max = capabilities.zoom.max || 3;
                    zoomSlider.step = capabilities.zoom.step || 0.1;
                    zoomSlider.value = this.currentZoom;
                } else {
                    console.log('Zoom not supported or elements not found');
                }

                // Show/hide flash button based on support
                const flashBtn = document.getElementById('flash-btn');
                if (flashBtn) {
                    if (capabilities.torch) {
                        console.log('Flash supported');
                        flashBtn.style.display = 'flex';
                    } else {
                        console.log('Flash not supported');
                        flashBtn.style.display = 'none';
                    }
                }

                // Apply initial settings
                this.applyVideoSettings();
            } catch (capError) {
                console.warn('Could not get camera capabilities:', capError);
                // Hide advanced controls if capabilities are not available
                const zoomControl = document.getElementById('zoom-control');
                if (zoomControl) zoomControl.style.display = 'none';
            }

            // Show camera view
            if (cameraContainer) cameraContainer.style.display = 'block';
            if (startBtn) startBtn.style.display = 'none';
            if (takeBtn) takeBtn.style.display = 'block';

            console.log('Camera started successfully');

        } catch (error) {
            console.error('Camera error:', error);
            console.error('Error stack:', error.stack);
            this.showError('Kunne ikke åpne kamera: ' + error.message);
        }
    }

    applyVideoSettings() {
        if (!this.videoTrack) return;

        try {
            const capabilities = this.videoTrack.getCapabilities();
            if (!capabilities) return;

            const settings = {};

            // Apply zoom
            if (capabilities.zoom) {
                settings.zoom = this.currentZoom;
            }

            // Apply torch/flash
            if (capabilities.torch) {
                settings.torch = this.flashEnabled;
            }

            // Apply focus mode
            if (capabilities.focusMode && Array.isArray(capabilities.focusMode) && capabilities.focusMode.includes('continuous')) {
                settings.focusMode = 'continuous';
            }

            if (Object.keys(settings).length > 0) {
                this.videoTrack.applyConstraints({ advanced: [settings] })
                    .catch(err => console.warn('Could not apply settings:', err));
            }
        } catch (error) {
            console.warn('Error applying video settings:', error);
        }
    }

    toggleFlash() {
        this.flashEnabled = !this.flashEnabled;
        this.applyVideoSettings();

        const flashBtn = document.getElementById('flash-btn');
        if (flashBtn) {
            if (this.flashEnabled) {
                flashBtn.classList.add('active');
            } else {
                flashBtn.classList.remove('active');
            }
        }
    }

    async switchCamera() {
        if (!this.stream) return;

        this.currentFacingMode = this.currentFacingMode === 'environment' ? 'user' : 'environment';

        // Stop current stream
        this.stream.getTracks().forEach(track => track.stop());

        // Restart with new facing mode
        await this.startCamera();
    }

    setZoom(value) {
        this.currentZoom = parseFloat(value);
        this.applyVideoSettings();

        const label = document.getElementById('zoom-label');
        if (label) {
            label.textContent = `Zoom: ${this.currentZoom.toFixed(1)}x`;
        }
    }

    takePhoto() {
        try {
            const video = document.getElementById('camera-preview');
            const canvas = document.getElementById('camera-canvas');

            if (!video || !canvas) {
                throw new Error('Video or canvas element not found');
            }

            const ctx = canvas.getContext('2d');
            if (!ctx) {
                throw new Error('Could not get canvas context');
            }

            // Set canvas dimensions to match video
            canvas.width = video.videoWidth || 1920;
            canvas.height = video.videoHeight || 1080;

            // Draw video frame to canvas
            ctx.drawImage(video, 0, 0);

            // Stop camera
            if (this.stream) {
                this.stream.getTracks().forEach(track => track.stop());
                this.stream = null;
                this.videoTrack = null;
            }

            // Hide camera view
            const cameraContainer = document.getElementById('camera-preview-container');
            const takeBtn = document.getElementById('take-photo-btn');
            if (cameraContainer) cameraContainer.style.display = 'none';
            if (takeBtn) takeBtn.style.display = 'none';

            // Load image into editor
            const imageData = canvas.toDataURL('image/jpeg', 0.95);
            this.loadImageIntoEditor(imageData);
        } catch (error) {
            console.error('Error taking photo:', error);
            this.showError('Kunne ikke ta bilde: ' + error.message);
        }
    }

    loadImageIntoEditor(imageData) {
        const img = new Image();
        img.onload = () => {
            try {
                this.currentImage = img;
                this.currentRotation = 0;
                this.cropMode = false;

                // Initialize editor canvas
                this.editorCanvas = document.getElementById('image-editor-canvas');
                if (!this.editorCanvas) {
                    throw new Error('Editor canvas not found');
                }

                this.editorCtx = this.editorCanvas.getContext('2d');
                if (!this.editorCtx) {
                    throw new Error('Could not get editor canvas context');
                }

                // Set canvas size
                const maxWidth = 600;
                const scale = Math.min(1, maxWidth / img.width);
                this.editorCanvas.width = img.width * scale;
                this.editorCanvas.height = img.height * scale;

                // Draw image
                this.redrawEditor();

                // Show editor
                const previewContainer = document.getElementById('image-preview-container');
                const uploadSection = document.getElementById('upload-form-section');
                const dateInput = document.getElementById('receipt-date');

                if (previewContainer) previewContainer.style.display = 'block';
                if (uploadSection) uploadSection.style.display = 'block';

                // Set today's date as default
                if (dateInput) {
                    dateInput.value = new Date().toISOString().split('T')[0];
                }
            } catch (error) {
                console.error('Error loading image into editor:', error);
                this.showError('Kunne ikke laste bilde: ' + error.message);
            }
        };
        img.onerror = () => {
            this.showError('Kunne ikke laste bildedata');
        };
        img.src = imageData;
    }

    redrawEditor() {
        if (!this.currentImage || !this.editorCanvas || !this.editorCtx) return;

        const canvas = this.editorCanvas;
        const ctx = this.editorCtx;

        // Save current dimensions
        const originalWidth = canvas.width;
        const originalHeight = canvas.height;

        // Adjust canvas size for rotation
        if (Math.abs(this.currentRotation) === 90 || Math.abs(this.currentRotation) === 270) {
            canvas.width = originalHeight;
            canvas.height = originalWidth;
        } else {
            canvas.width = originalWidth;
            canvas.height = originalHeight;
        }

        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Save context
        ctx.save();

        // Apply rotation
        if (this.currentRotation !== 0) {
            ctx.translate(canvas.width / 2, canvas.height / 2);
            ctx.rotate((this.currentRotation * Math.PI) / 180);

            // Calculate scaled dimensions
            const maxWidth = 600;
            const scale = Math.min(1, maxWidth / this.currentImage.width);
            const scaledWidth = this.currentImage.width * scale;
            const scaledHeight = this.currentImage.height * scale;

            ctx.drawImage(this.currentImage, -scaledWidth / 2, -scaledHeight / 2, scaledWidth, scaledHeight);
        } else {
            ctx.drawImage(this.currentImage, 0, 0, canvas.width, canvas.height);
        }

        // Restore context
        ctx.restore();
    }

    rotateImage(degrees) {
        this.currentRotation = (this.currentRotation + degrees) % 360;
        if (this.currentRotation < 0) this.currentRotation += 360;
        this.redrawEditor();
    }

    toggleCrop() {
        this.cropMode = !this.cropMode;
        const overlay = document.getElementById('crop-overlay');

        if (this.cropMode) {
            // Show crop overlay
            overlay.classList.add('active');
            this.initializeCropArea();
            this.setupCropHandlers();
            this.showSuccess('Juster beskjæringsområdet og trykk "Beskjær" igjen');
        } else {
            // Apply crop
            overlay.classList.remove('active');
            this.applyCrop();
        }
    }

    initializeCropArea() {
        if (!this.editorCanvas) return;

        const container = document.getElementById('editor-container');
        const cropAreaEl = document.getElementById('crop-area');

        if (!container || !cropAreaEl) return;

        const rect = container.getBoundingClientRect();

        // Set initial crop area (90% of image, centered)
        this.cropArea = { x: 5, y: 5, width: 90, height: 90 };
        this.updateCropAreaDisplay();
    }

    updateCropAreaDisplay() {
        const container = document.getElementById('editor-container');
        const cropAreaEl = document.getElementById('crop-area');

        if (!container || !cropAreaEl) return;

        const rect = container.getBoundingClientRect();

        cropAreaEl.style.left = `${this.cropArea.x}%`;
        cropAreaEl.style.top = `${this.cropArea.y}%`;
        cropAreaEl.style.width = `${this.cropArea.width}%`;
        cropAreaEl.style.height = `${this.cropArea.height}%`;
    }

    setupCropHandlers() {
        const cropAreaEl = document.getElementById('crop-area');
        if (!cropAreaEl) return;

        // Remove existing listeners
        const newCropArea = cropAreaEl.cloneNode(true);
        cropAreaEl.parentNode.replaceChild(newCropArea, cropAreaEl);

        // Move crop area
        newCropArea.addEventListener('mousedown', (e) => this.startDragCrop(e));
        newCropArea.addEventListener('touchstart', (e) => this.startDragCrop(e), { passive: false });

        // Resize handles
        const handles = newCropArea.querySelectorAll('.crop-handle');
        handles.forEach(handle => {
            handle.addEventListener('mousedown', (e) => this.startResizeCrop(e, handle));
            handle.addEventListener('touchstart', (e) => this.startResizeCrop(e, handle), { passive: false });
        });

        // Global move/end handlers
        document.addEventListener('mousemove', (e) => this.onCropMove(e));
        document.addEventListener('touchmove', (e) => this.onCropMove(e), { passive: false });
        document.addEventListener('mouseup', (e) => this.endCropDrag(e));
        document.addEventListener('touchend', (e) => this.endCropDrag(e));
    }

    startDragCrop(e) {
        if (e.target.classList.contains('crop-handle')) return; // Don't drag on handles

        e.preventDefault();
        e.stopPropagation();

        this.isDraggingCrop = true;
        const point = this.getEventPoint(e);
        this.dragStartX = point.x;
        this.dragStartY = point.y;
    }

    startResizeCrop(e, handle) {
        e.preventDefault();
        e.stopPropagation();

        this.isResizingCrop = true;
        this.resizeHandle = handle.classList[1]; // nw, ne, sw, se, n, s, w, e
        const point = this.getEventPoint(e);
        this.dragStartX = point.x;
        this.dragStartY = point.y;
    }

    onCropMove(e) {
        if (!this.isDraggingCrop && !this.isResizingCrop) return;

        e.preventDefault();

        const point = this.getEventPoint(e);
        const container = document.getElementById('editor-container');
        if (!container) return;

        const rect = container.getBoundingClientRect();
        const deltaX = ((point.x - this.dragStartX) / rect.width) * 100;
        const deltaY = ((point.y - this.dragStartY) / rect.height) * 100;

        if (this.isDraggingCrop) {
            // Move crop area
            this.cropArea.x = Math.max(0, Math.min(100 - this.cropArea.width, this.cropArea.x + deltaX));
            this.cropArea.y = Math.max(0, Math.min(100 - this.cropArea.height, this.cropArea.y + deltaY));
        } else if (this.isResizingCrop) {
            // Resize crop area based on handle
            const handle = this.resizeHandle;

            if (handle.includes('n')) {
                const newY = this.cropArea.y + deltaY;
                const newHeight = this.cropArea.height - deltaY;
                if (newY >= 0 && newHeight >= 10) {
                    this.cropArea.y = newY;
                    this.cropArea.height = newHeight;
                }
            }
            if (handle.includes('s')) {
                const newHeight = this.cropArea.height + deltaY;
                if (this.cropArea.y + newHeight <= 100 && newHeight >= 10) {
                    this.cropArea.height = newHeight;
                }
            }
            if (handle.includes('w')) {
                const newX = this.cropArea.x + deltaX;
                const newWidth = this.cropArea.width - deltaX;
                if (newX >= 0 && newWidth >= 10) {
                    this.cropArea.x = newX;
                    this.cropArea.width = newWidth;
                }
            }
            if (handle.includes('e')) {
                const newWidth = this.cropArea.width + deltaX;
                if (this.cropArea.x + newWidth <= 100 && newWidth >= 10) {
                    this.cropArea.width = newWidth;
                }
            }
        }

        this.updateCropAreaDisplay();
        this.dragStartX = point.x;
        this.dragStartY = point.y;
    }

    endCropDrag(e) {
        this.isDraggingCrop = false;
        this.isResizingCrop = false;
        this.resizeHandle = null;
    }

    getEventPoint(e) {
        if (e.touches && e.touches.length > 0) {
            return { x: e.touches[0].clientX, y: e.touches[0].clientY };
        }
        return { x: e.clientX, y: e.clientY };
    }

    applyCrop() {
        if (!this.editorCanvas || !this.currentImage) return;

        // Calculate crop area in pixels
        const sourceCanvas = this.editorCanvas;
        const cropX = (this.cropArea.x / 100) * sourceCanvas.width;
        const cropY = (this.cropArea.y / 100) * sourceCanvas.height;
        const cropWidth = (this.cropArea.width / 100) * sourceCanvas.width;
        const cropHeight = (this.cropArea.height / 100) * sourceCanvas.height;

        // Create temporary canvas with cropped content
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = cropWidth;
        tempCanvas.height = cropHeight;
        const tempCtx = tempCanvas.getContext('2d');

        // Draw cropped portion
        tempCtx.drawImage(
            sourceCanvas,
            cropX, cropY, cropWidth, cropHeight,
            0, 0, cropWidth, cropHeight
        );

        // Load cropped image as new current image
        const croppedDataUrl = tempCanvas.toDataURL('image/jpeg', 0.95);
        const img = new Image();
        img.onload = () => {
            this.currentImage = img;
            this.currentRotation = 0;

            // Reset crop area to full size
            this.cropArea = { x: 5, y: 5, width: 90, height: 90 };

            // Redraw with cropped image
            const maxWidth = 600;
            const scale = Math.min(1, maxWidth / img.width);
            this.editorCanvas.width = img.width * scale;
            this.editorCanvas.height = img.height * scale;

            this.redrawEditor();
            this.showSuccess('Bildet er beskåret!');
        };
        img.src = croppedDataUrl;
    }

    enhanceImage() {
        if (!this.currentImage || !this.editorCanvas) return;

        const canvas = this.editorCanvas;
        const ctx = this.editorCtx;

        // Get image data
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const data = imageData.data;

        // Apply auto-contrast enhancement
        // Find min and max brightness
        let min = 255, max = 0;
        for (let i = 0; i < data.length; i += 4) {
            const brightness = (data[i] + data[i + 1] + data[i + 2]) / 3;
            min = Math.min(min, brightness);
            max = Math.max(max, brightness);
        }

        // Stretch contrast
        const range = max - min;
        if (range > 0) {
            for (let i = 0; i < data.length; i += 4) {
                data[i] = ((data[i] - min) * 255) / range;     // R
                data[i + 1] = ((data[i + 1] - min) * 255) / range; // G
                data[i + 2] = ((data[i + 2] - min) * 255) / range; // B
            }
        }

        // Apply slight sharpening
        const sharpenKernel = [
            0, -1, 0,
            -1, 5, -1,
            0, -1, 0
        ];

        const tempData = new Uint8ClampedArray(data);
        const width = canvas.width;

        for (let y = 1; y < canvas.height - 1; y++) {
            for (let x = 1; x < width - 1; x++) {
                for (let c = 0; c < 3; c++) {
                    let sum = 0;
                    for (let ky = -1; ky <= 1; ky++) {
                        for (let kx = -1; kx <= 1; kx++) {
                            const idx = ((y + ky) * width + (x + kx)) * 4 + c;
                            sum += tempData[idx] * sharpenKernel[(ky + 1) * 3 + (kx + 1)];
                        }
                    }
                    data[(y * width + x) * 4 + c] = Math.max(0, Math.min(255, sum));
                }
            }
        }

        ctx.putImageData(imageData, 0, 0);
        this.showSuccess('Bildet er forbedret!');
    }

    retakePhoto() {
        this.capturedImage = null;
        this.currentImage = null;
        this.currentRotation = 0;
        this.cropMode = false;
        document.getElementById('image-preview-container').style.display = 'none';
        document.getElementById('upload-form-section').style.display = 'none';
        document.getElementById('start-camera-btn').style.display = 'block';
    }

    handleFileSelect(event) {
        const file = event.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (e) => {
            this.loadImageIntoEditor(e.target.result);
        };
        reader.readAsDataURL(file);
    }

    async uploadReceipt() {
        if (!this.editorCanvas) {
            this.showError('Ingen bilde valgt');
            return;
        }

        console.log('Upload: token=', this.token ? 'set' : 'missing');
        console.log('Upload: ledger=', this.ledger);

        if (!this.ledger) {
            this.showError('Ingen ledger valgt. Prøv å logge ut og inn igjen.');
            return;
        }

        try {
            this.showLoading(true);

            // Convert canvas to blob
            const blob = await new Promise(resolve => {
                this.editorCanvas.toBlob(resolve, 'image/jpeg', 0.95);
            });

            const formData = new FormData();
            formData.append('file', blob, 'receipt.jpg');

            const receiptDate = document.getElementById('receipt-date').value;
            const amount = document.getElementById('receipt-amount').value;
            const description = document.getElementById('receipt-description').value;

            if (receiptDate) formData.append('receipt_date', receiptDate);
            if (amount) formData.append('amount', amount);
            if (description) formData.append('description', description);

            const response = await fetch(`${this.baseURL}/receipts/upload`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${this.token}`,
                    'X-Ledger-ID': String(this.ledger)
                },
                body: formData
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Opplasting feilet');
            }

            this.showLoading(false);
            this.showSuccessMessage();
        } catch (error) {
            this.showLoading(false);
            this.showError('Kunne ikke laste opp: ' + error.message);
        }
    }

    cancelUpload() {
        this.retakePhoto();
    }

    showSuccessMessage() {
        document.getElementById('camera-section').style.display = 'none';
        document.getElementById('upload-form-section').style.display = 'none';
        document.getElementById('success-message').style.display = 'block';
    }

    reset() {
        this.capturedImage = null;
        this.currentImage = null;
        this.currentRotation = 0;
        this.cropMode = false;
        this.editorCanvas = null;
        this.editorCtx = null;

        document.getElementById('image-preview-container').style.display = 'none';
        document.getElementById('upload-form-section').style.display = 'none';
        document.getElementById('success-message').style.display = 'none';
        document.getElementById('camera-section').style.display = 'block';
        document.getElementById('start-camera-btn').style.display = 'block';

        // Clear form
        document.getElementById('receipt-date').value = '';
        document.getElementById('receipt-amount').value = '';
        document.getElementById('receipt-description').value = '';
        document.getElementById('file-input').value = '';
    }

    showLoading(show) {
        document.getElementById('loading-overlay').style.display = show ? 'flex' : 'none';
    }

    showToast(message, type = 'info') {
        const container = this.getToastContainer();
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;

        const icon = type === 'error' ? '✗' : type === 'success' ? '✓' : 'ℹ';

        toast.innerHTML = `
            <span class="toast-icon">${icon}</span>
            <span class="toast-message">${message}</span>
            <button class="toast-close" onclick="this.parentElement.remove()">&times;</button>
        `;

        container.appendChild(toast);

        setTimeout(() => toast.classList.add('toast-show'), 10);

        setTimeout(() => {
            toast.classList.remove('toast-show');
            setTimeout(() => toast.remove(), 300);
        }, 5000);
    }

    getToastContainer() {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            document.body.appendChild(container);
        }
        return container;
    }

    showError(message) {
        this.showToast(message, 'error');
    }

    showSuccess(message) {
        this.showToast(message, 'success');
    }
}

// Initialize app
const mobileApp = new MobileApp();
window.mobileApp = mobileApp;
