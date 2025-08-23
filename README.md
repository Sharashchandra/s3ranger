# S3Ranger

A terminal-based user interface for browsing and managing AWS S3 buckets and objects. Built with Python and [Textual](https://textual.textualize.io/), s3ranger provides an intuitive way to interact with S3 storage directly from your terminal.

![s3ranger Screenshot](pics/main_screen.png)
![s3ranger Screenshot](pics/download.png)
![s3ranger Screenshot](pics/upload.png)
![s3ranger Screenshot](pics/delete.png)
![s3ranger Screenshot](pics/rename.png)

## Features

- 🗂️ **Browse S3 buckets and objects** with an intuitive file manager interface
- 📁 **Navigate folder structures** seamlessly
- ⬆️ **Upload files and directories** to S3
- ⬇️ **Download files and directories** from S3
- 🗑️ **Delete objects and folders** with confirmation prompts
- ✏️ **Rename files and folders** with conflict detection
- 🔍 **Filter and search** through buckets
- 📊 **Sort objects** by name, type, modification date, or size
- 🎨 **Multiple themes** (GitHub Dark, Dracula, Solarized, Sepia)
- ⚙️ **Flexible configuration** via CLI arguments, config files, or environment variables
- 🔐 **Multiple authentication methods** (profiles, access keys, session tokens)
- 🌐 **S3-compatible services** support (LocalStack, MinIO, etc.)

## Installation

### Using pip

```bash
pip install s3ranger
```

### Using pipx (recommended for CLI tools)

```bash
pipx install s3ranger
```

### Using uv

```bash
uv add s3ranger
```

### From source

```bash
git clone https://github.com/Sharashchandra/s3ranger.git
cd s3ranger
pip install -e .
```

## Quick Start

### 1. Configure AWS credentials

First, ensure you have AWS credentials configured. You can use any of these methods:

#### Option A: AWS CLI (recommended)

```bash
aws configure
```

#### Option B: Environment variables

```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
```

#### Option C: s3ranger configuration

```bash
s3ranger configure
```

### 2. Launch s3ranger

```bash
s3ranger
```

## Usage

### Basic Commands

```bash
# Launch the TUI
s3ranger

# Launch with specific AWS profile
s3ranger --profile-name myprofile

# Launch with custom endpoint (for S3-compatible services)
s3ranger --endpoint-url https://s3.amazonaws.com --region-name us-west-2

# Launch with specific theme
s3ranger --theme dracula

# Show help
s3ranger --help

# Interactive configuration
s3ranger configure
```

### Command Line Options

| Option                    | Description             | Example                                                            |
| ------------------------- | ----------------------- | ------------------------------------------------------------------ |
| `--endpoint-url`          | Custom S3 endpoint URL  | `--endpoint-url https://minio.example.com`                         |
| `--region-name`           | AWS region name         | `--region-name us-west-2`                                          |
| `--profile-name`          | AWS profile name        | `--profile-name production`                                        |
| `--aws-access-key-id`     | AWS access key ID       | `--aws-access-key-id AKIAIOSFODNN7EXAMPLE`                         |
| `--aws-secret-access-key` | AWS secret access key   | `--aws-secret-access-key wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `--aws-session-token`     | AWS session token       | `--aws-session-token token123`                                     |
| `--theme`                 | UI theme                | `--theme "github dark"`                                            |
| `--config`                | Configuration file path | `--config ~/.s3ranger.config`                                         |

### Keyboard Shortcuts

| Key      | Action                                   |
| -------- | ---------------------------------------- |
| `Tab`    | Switch between panels                    |
| `Enter`  | Enter bucket/folder or download file     |
| `Ctrl+R` | Refresh current view                     |
| `Ctrl+F` | Filter/search                            |
| `Ctrl+S` | Sort objects (by name, type, date, size) |
| `Ctrl+H` | Show help modal                          |
| `Ctrl+Q` | Quit application                         |
| `Ctrl+P` | Open command palette                     |
| `U`      | Upload file/folder                       |
| `D`      | Download selected item                   |
| `Delete` | Delete selected item                     |
| `Ctrl+K` | Rename selected item                     |
| `F1`     | Help                                     |

### Working with S3-Compatible Services

s3ranger works with any S3-compatible service:

#### LocalStack

```bash
s3ranger --endpoint-url http://localhost:4566 --region-name us-east-1
```

## Configuration

### Configuration File

s3ranger can be configured using a TOML configuration file located at `~/.s3ranger.config`:

```toml
# AWS Configuration
endpoint_url = "https://localhost:4566"
region_name = "us-east-1"
profile_name = "default"

# Optional: Direct credentials
# aws_access_key_id = "your_access_key"
# aws_secret_access_key = "your_secret_key"
# aws_session_token = "your_session_token"

# UI Configuration
theme = "Github Dark"
```

### Environment Variables

s3ranger respects standard AWS environment variables:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN`
- `AWS_DEFAULT_REGION`
- `AWS_PROFILE`

### Configuration Priority

Configuration is applied in the following order (highest to lowest priority):

1. Command line arguments
2. Environment variables
3. Configuration file
4. AWS credentials file (`~/.aws/credentials`)
5. Default values

## Themes

s3ranger comes with several built-in themes:

- **GitHub Dark** (default) - Dark theme inspired by GitHub's interface
- **Dracula** - Popular dark theme with purple accents
- **Solarized** - The classic Solarized color scheme
- **Sepia** - Warm, vintage-inspired theme

Change themes using:

```bash
s3ranger --theme dracula
```

Or through the configuration file:

```toml
theme = "Dracula"
```

## Development

### Prerequisites

- Python 3.11 or higher
- uv (recommended) or pip

### Setup

```bash
git clone https://github.com/Sharashchandra/s3ranger.git
cd s3ranger

# Using uv
uv sync
uv run s3ranger

# Using pip
pip install -e ".[dev]"
python -m s3ranger.main
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [Textual](https://textual.textualize.io/) by Textualize
- Uses [boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html) for AWS S3 integration
- CLI powered by [Click](https://click.palletsprojects.com/)
- File picker functionality provided by [textual-fspicker](https://github.com/davep/textual-fspicker)

## Support

If you encounter any issues or have questions:

- 🐛 [Report bugs](https://github.com/Sharashchandra/s3ranger/issues)
- 💡 [Request features](https://github.com/Sharashchandra/s3ranger/issues)
- 💬 [Discussions](https://github.com/Sharashchandra/s3ranger/discussions)
