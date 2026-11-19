// SPDX-License-Identifier: MIT OR Apache-2.0
//! SigmaOS-greeter — Slick login greeter with user list & a11y.
//!
//! Provides user identity listing, session launcher choices (Wayland compositor / X11),
//! accessibility presets (high contrast, large text, screen reader), and auth lifecycle.
//!
//! Inspired by Omarchy's frictionless display greeter, Hyprland's `hyprlock` minimalist layout,
//! and Catppuccin Mocha's warm login palette.
//!
//! Principles: fail-safe auth state machine, pure `std`, zero `unsafe`.

#![forbid(unsafe_code)]

use std::collections::HashMap;
use std::fmt;

// ── Error types ──────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum GreeterError {
    UserNotFound(String),
    SessionTypeNotSupported(String),
    AuthenticationInProgress,
    InvalidCredential,
    NoUsersConfigured,
}

impl fmt::Display for GreeterError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::UserNotFound(u) => write!(f, "user '{u}' not found in user database"),
            Self::SessionTypeNotSupported(s) => write!(f, "session type '{s}' not supported"),
            Self::AuthenticationInProgress => write!(f, "authentication attempt already in progress"),
            Self::InvalidCredential => write!(f, "invalid login credentials supplied"),
            Self::NoUsersConfigured => write!(f, "no display manager users configured"),
        }
    }
}

impl std::error::Error for GreeterError {}

// ── User and Accessibility ───────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SessionType {
    WaylandHyprland,
    WaylandSway,
    X11Generic,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct UserEntry {
    pub username: String,
    pub real_name: String,
    pub avatar_path: Option<String>,
    pub preferred_session: SessionType,
}

impl UserEntry {
    pub fn new(username: impl Into<String>, real_name: impl Into<String>) -> Self {
        Self {
            username: username.into(),
            real_name: real_name.into(),
            avatar_path: None,
            preferred_session: SessionType::WaylandHyprland,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct AccessibilityConfig {
    pub high_contrast: bool,
    pub large_font: bool,
    pub screen_reader: bool,
    pub onscreen_keyboard: bool,
}

// ── Authentication State Machine ─────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum AuthState {
    #[default]
    Idle,
    Authenticating,
    Authenticated,
    AuthFailed,
}

#[derive(Debug, Default)]
pub struct GreeterSession {
    users: HashMap<String, UserEntry>,
    selected_user: Option<String>,
    active_session_type: SessionType,
    pub a11y: AccessibilityConfig,
    state: AuthState,
}

impl Default for SessionType {
    fn default() -> Self {
        Self::WaylandHyprland
    }
}

impl GreeterSession {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn register_user(&mut self, user: UserEntry) {
        if self.selected_user.is_none() {
            self.selected_user = Some(user.username.clone());
        }
        self.users.insert(user.username.clone(), user);
    }

    pub fn select_user(&mut self, username: &str) -> Result<(), GreeterError> {
        if !self.users.contains_key(username) {
            return Err(GreeterError::UserNotFound(username.into()));
        }
        self.selected_user = Some(username.to_string());
        self.state = AuthState::Idle;
        Ok(())
    }

    pub fn authenticate(&mut self, password: &str) -> Result<AuthState, GreeterError> {
        if self.state == AuthState::Authenticating {
            return Err(GreeterError::AuthenticationInProgress);
        }
        let user = self.selected_user.as_deref().ok_or(GreeterError::NoUsersConfigured)?;
        if !self.users.contains_key(user) {
            return Err(GreeterError::UserNotFound(user.into()));
        }

        self.state = AuthState::Authenticating;
        if password.is_empty() {
            self.state = AuthState::AuthFailed;
            return Err(GreeterError::InvalidCredential);
        }

        self.state = AuthState::Authenticated;
        Ok(self.state)
    }

    pub fn state(&self) -> AuthState {
        self.state
    }

    pub fn selected_user(&self) -> Option<&UserEntry> {
        self.selected_user.as_deref().and_then(|u| self.users.get(u))
    }
}

// ── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn register_and_auto_select_first_user() {
        // Arrange
        let mut greeter = GreeterSession::new();
        let u1 = UserEntry::new("alice", "Alice Wonderland");
        let u2 = UserEntry::new("bob", "Bob Builder");

        // Act
        greeter.register_user(u1);
        greeter.register_user(u2);

        // Assert
        assert_eq!(greeter.selected_user().unwrap().username, "alice");
    }

    #[test]
    fn switch_selected_user_success_and_missing() {
        // Arrange
        let mut greeter = GreeterSession::new();
        greeter.register_user(UserEntry::new("charlie", "Charlie"));

        // Act
        let ok = greeter.select_user("charlie");
        let missing = greeter.select_user("nonexistent");

        // Assert
        assert!(ok.is_ok());
        assert_eq!(missing, Err(GreeterError::UserNotFound("nonexistent".into())));
    }

    #[test]
    fn authentication_happy_path() {
        // Arrange
        let mut greeter = GreeterSession::new();
        greeter.register_user(UserEntry::new("dan", "Dan"));

        // Act
        let res = greeter.authenticate("correct-horse-battery");

        // Assert
        assert_eq!(res, Ok(AuthState::Authenticated));
        assert_eq!(greeter.state(), AuthState::Authenticated);
    }

    #[test]
    fn authentication_empty_password_fails() {
        // Arrange
        let mut greeter = GreeterSession::new();
        greeter.register_user(UserEntry::new("dan", "Dan"));

        // Act
        let res = greeter.authenticate("");

        // Assert
        assert_eq!(res, Err(GreeterError::InvalidCredential));
        assert_eq!(greeter.state(), AuthState::AuthFailed);
    }

    #[test]
    fn accessibility_defaults_and_toggle() {
        // Arrange
        let mut greeter = GreeterSession::new();
        assert!(!greeter.a11y.high_contrast);

        // Act
        greeter.a11y.high_contrast = true;
        greeter.a11y.large_font = true;

        // Assert
        assert!(greeter.a11y.high_contrast);
        assert!(greeter.a11y.large_font);
    }

    #[test]
    fn error_display_formatting() {
        // Arrange
        let err = GreeterError::UserNotFound("ghost".into());
        // Act & Assert
        assert_eq!(format!("{err}"), "user 'ghost' not found in user database");
    }
}
