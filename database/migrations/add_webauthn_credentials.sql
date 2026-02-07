-- Add WebAuthn credentials table for passkey authentication
CREATE TABLE IF NOT EXISTS webauthn_credentials (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    credential_id VARCHAR(1024) NOT NULL UNIQUE,
    public_key TEXT NOT NULL,
    sign_count INT NOT NULL DEFAULT 0,
    credential_name VARCHAR(255),
    transports JSON,
    aaguid VARCHAR(36),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP NULL,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_credential_id (credential_id(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
