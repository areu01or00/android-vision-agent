# Contributing to Android AI Agent

Thank you for considering contributing to the Android AI Agent project! This document provides guidelines and instructions for contributing.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```
   git clone https://github.com/YOUR-USERNAME/android-ai-agent.git
   cd android-ai-agent
   ```
3. **Set up the development environment**:
   ```
   pip install -r requirements.txt
   ```
4. **Create a branch** for your feature or bugfix:
   ```
   git checkout -b feature/your-feature-name
   ```

## Development Guidelines

### Code Style
- Follow PEP 8 style guidelines for Python code
- Use descriptive variable names and add comments where necessary
- Add docstrings to all functions and classes

### Testing
- Test your changes on at least one Android device
- Document any limitations or specific requirements for your implementation
- If adding new features, include example commands that demonstrate the functionality

### Commit Messages
- Use clear, descriptive commit messages
- Reference issue numbers when applicable
- Use present tense ("Add feature" not "Added feature")

## Pull Request Process

1. **Update the README.md** with details of your changes if relevant
2. **Ensure your code works** with the latest version of the main branch
3. **Submit your Pull Request** with a clear description of:
   - What problem your PR solves
   - How it implements the solution
   - Any dependencies added or removed
   - Screenshots or videos demonstrating the feature (if applicable)

## Recent Improvements

The Android AI Agent has recently been enhanced with several key improvements:

- **Enhanced System Prompt**: Added detailed guidance for task execution
- **Improved Search Task Handling**: Added verification for search task completion
- **Fixed Typing Command**: Improved text input reliability
- **Added Press Enter Action**: New action type for search submissions
- **Task-Specific Context**: Added specialized handling for common tasks

When contributing, please ensure your changes align with these improvements and maintain backward compatibility.

## Areas for Improvement

Here are some areas where contributions are particularly welcome:

- **Enhanced Task Verification**: Improve verification for different types of tasks beyond search
- **App-Specific Handlers**: Add specialized handling for more popular apps
- **UI Element Recognition**: Improve the accuracy of identifying UI elements
- **Error Handling**: Enhance error recovery for different Android device models
- **Performance Optimizations**: Reduce API calls and improve response time
- **Documentation and Examples**: Expand documentation with more use cases
- **Testing Framework**: Develop automated testing for the agent
- **Multi-Language Support**: Add support for non-English languages
- **Accessibility Features**: Improve interaction with accessibility elements
- **Search Result Analysis**: Enhance the verification of search results quality

## Code of Conduct

- Be respectful and inclusive in your communications
- Accept constructive criticism gracefully
- Focus on what is best for the community and project

## Questions?

If you have questions or need assistance, please open an issue with the "question" label.

Thank you for contributing to make Android AI Agent better for everyone!