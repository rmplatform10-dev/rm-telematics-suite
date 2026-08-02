# 📁 rm-simulator-core

This module serves as the automated testing utility for the telematics network. It manages multiple vehicle profiles concurrently to safely stress-test your ingestion servers.

## 🗺️ Module Architecture Tree
\\\	ext
rm-simulator-core/
├── 📄 README.md                         \)
*   \status\ : Displays an overview statement highlighting telemetry items for all active hardware nodes.
*   \status <sim_id>\ : Extracts specific position mappings and network connection profiles for a single item.
*   \sms <sim_id> <command>\ : Forwards standard system instructions (\server\, \eboot\, \loc\) straight to the script's receiver.
*   \exit\ : Clears background threads and ends terminal loops cleanly.