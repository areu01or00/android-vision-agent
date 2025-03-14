# Changelog

All notable changes to the Android AI Agent project will be documented in this file.

## [1.1.0] - 2024-03-14

### Added
- Added `verify_search_results` method to ensure search tasks are properly completed
- Added `press_enter` action for simulating Enter key presses
- Added task-specific context for Chrome, Gmail, and Twitter tasks
- Added detailed guidance for search tasks in the system prompt
- Added search task completion verification in the `run_task` method

### Fixed
- Fixed typing command to avoid shell interpretation issues
- Fixed search task completion verification to ensure results are displayed
- Fixed handling of special characters in text input

### Changed
- Enhanced system prompt with more detailed guidance for task execution
- Improved search task handling with verification steps
- Updated documentation to reflect recent changes
- Added more detailed error messages and suggestions for repetitive actions

## [1.0.0] - 2023-12-15

### Added
- Initial release of Android AI Agent
- Dual-model architecture with vision and planning models
- Hybrid command-vision approach
- XML view hierarchy analysis
- Flexible LLM provider support (OpenAI and OpenRouter)
- Intelligent screen analysis
- Smart task planning
- Robust error recovery
- Detailed session logs
- Screen recording during agent sessions