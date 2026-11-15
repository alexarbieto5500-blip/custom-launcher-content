# Privacy notice — Custom Launcher

Development-stage notice. This document describes current functionality and intended authentication design, not a completed production authentication system.

## Current functionality

The launcher stores local profile names, settings, installed game content and diagnostic logs on the user's device. It contacts external content providers to download game files and updates. Those providers may process network information such as IP addresses under their own privacy policies.

## Planned Microsoft authentication

Users will authenticate through Microsoft's official browser sign-in page. The launcher is intended to process authorization tokens, Minecraft entitlement information and player profile data (including name and UUID) only as needed to establish and maintain a game session. Microsoft passwords will not be collected by the launcher. Secure local token storage and session renewal are planned and have not yet been implemented.

## Logs and data removal

Diagnostic logs are stored locally. Game and third-party component logs may contain personal information; users should review logs before sharing them. Local launcher data can be removed by deleting the relevant application data after closing the launcher and game; this may also remove settings, downloaded content and saved worlds, so backups are recommended.

## External providers

Microsoft authentication and Minecraft services are subject to the Microsoft Privacy Statement: https://privacy.microsoft.com/privacystatement. GitHub-hosted content is subject to GitHub's applicable privacy terms.

## Contact and updates

Project questions and privacy concerns may be directed to the repository owner via their GitHub profile. This notice will be updated before public release to reflect the final implementation, retention practices and contact arrangements.
