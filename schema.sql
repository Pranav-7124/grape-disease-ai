-- ============================================================
-- Grape AI App - Database Schema
-- ============================================================

CREATE DATABASE IF NOT EXISTS `app` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `app`;

-- -----------------------------------------------
-- USERS: anonymized with UUID, bcrypt passwords
-- -----------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    anon_id      VARCHAR(36)  UNIQUE NOT NULL,   -- UUID, used in all logs
    username     VARCHAR(80)  UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------
-- PREDICTION LOGS: weather + ML output per user
-- -----------------------------------------------
CREATE TABLE IF NOT EXISTS prediction_logs (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    anon_id           VARCHAR(36)  NOT NULL,
    location          VARCHAR(100),
    temperature       FLOAT,
    humidity          FLOAT,
    rainfall          FLOAT,
    growth_stage      VARCHAR(50),
    predicted_disease VARCHAR(100),
    predicted_risk    VARCHAR(50),
    logged_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_anon   (anon_id),
    INDEX idx_logged (logged_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------
-- SCAN LOGS: camera AI analysis per user
-- -----------------------------------------------
CREATE TABLE IF NOT EXISTS scan_logs (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    anon_id          VARCHAR(36) NOT NULL,
    disease_detected VARCHAR(200),
    logged_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_anon (anon_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------
-- MODEL TRAINING LOG: self-training history
-- -----------------------------------------------
CREATE TABLE IF NOT EXISTS model_train_log (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    trained_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    samples_used INT DEFAULT 0,
    accuracy     FLOAT DEFAULT 0.0,
    trigger_type VARCHAR(20) DEFAULT 'scheduled'  -- 'scheduled' or 'manual'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
