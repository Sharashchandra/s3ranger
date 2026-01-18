# S3Ranger

A terminal-based user interface for browsing and managing AWS S3 buckets and objects. Built with Python and [Textual](https://textual.textualize.io/), s3ranger provides an intuitive way to interact with S3 storage directly from your terminal.

![s3ranger Screenshot](pics/main_screen.png)
![s3ranger Screenshot](pics/rename.png)
![s3ranger Screenshot](pics/upload.png)
![s3ranger Screenshot](pics/download.png)
![s3ranger Screenshot](pics/multi_download.png)
![s3ranger Screenshot](pics/delete.png)
![s3ranger Screenshot](pics/multi_delete.png)

## Features

- **Browse S3 buckets and objects** with an intuitive file manager interface
- **Navigate folder structures** seamlessly
- **Upload files and directories** to S3
- **Download files and directories** from S3
- **Copy and move files and folders** within the same bucket or across different S3 buckets
- **Delete objects and folders** with confirmation prompts
- **Rename files and folders** with conflict detection
- **Filter and search** through buckets
- **Sort objects** by name, type, modification date, or size
- **Lazy loading with pagination** - buckets and objects load progressively as you scroll
- **Multiple themes** (GitHub Dark, Dracula, Solarized, Sepia)
- **Flexible configuration** via CLI arguments or config files
- **Multiple authentication methods** (AWS profiles, CLI access keys)
- **S3-compatible services** support (LocalStack, MinIO, etc.)

## Installation

### Using pip

```bash
pip install s3ranger
```

### Using uv

```bash
# Install s3ranger globally
uv tool install s3ranger@latest

# Update to latest version
uv tool upgrade s3ranger
```

### From source

```bash
git clone https://github.com/Sharashchandra/s3ranger.git
cd s3ranger
pip install -e .
```

## Quick Start

### 1. Configure AWS Credentials

The recommended way to configure AWS credentials is using the AWS CLI:

```bash
aws configure
```

This sets up your default profile in `~/.aws/credentials` and `~/.aws/config`.

### 2. Launch s3ranger

```bash
s3ranger
```

That's it! s3ranger will use your default AWS profile automatically.

### Using Multiple AWS Profiles

If you work with multiple AWS accounts, you can set up named profiles and switch between them easily.

#### Setting up profiles with AWS CLI

```bash
# Configure your default profile
aws configure

# Configure additional named profiles
aws configure --profile work
aws configure --profile personal
```

#### AWS credentials file (`~/.aws/credentials`)

```ini
[default]
aws_access_key_id = AKIAIOSFODNN7EXAMPLE
aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY

[work]
aws_access_key_id = AKIAI44QH8DHBEXAMPLE
aws_secret_access_key = je7MtGbClwBF/2Zp9Utk/h3yCo8nvbEXAMPLEKEY

[personal]
aws_access_key_id = AKIAIOSFODNN7EXAMPLE2
aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLE2
```

#### AWS config file (`~/.aws/config`)

```ini
[default]
region = us-east-1
output = json

[profile work]
region = us-west-2
output = json

[profile personal]
region = eu-west-1
output = json
# Optional: for S3-compatible services
# endpoint_url = https://s3.custom-endpoint.com
```

#### Using profiles with s3ranger

```bash
# Use a specific profile via CLI
s3ranger --profile-name work

# Or set a default profile in s3ranger config file (~/.s3ranger.config)
# profile_name = "work"
```

### One-off Usage with Direct Credentials

For quick, one-time access, you can pass credentials directly via CLI:

```bash
s3ranger --aws-access-key-id AKIAIOSFODNN7EXAMPLE \
         --aws-secret-access-key wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

For temporary credentials (e.g., from AWS STS), include the session token:

```bash
s3ranger --aws-access-key-id AKIAIOSFODNN7EXAMPLE \
         --aws-secret-access-key wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY \
         --aws-session-token your-session-token
```

> **Note:** Direct credentials via CLI are useful for one-off usage but not recommended for regular use. Use AWS profiles for better security and convenience.

## Credential Priority

s3ranger resolves credentials in the following order (highest to lowest priority):

1. **CLI credentials** (`--aws-access-key-id` + `--aws-secret-access-key`)
2. **CLI profile** (`--profile-name`)
3. **Config file profile** (`profile_name` in `~/.s3ranger.config`)
4. **boto3 default resolution** - If none of the above are provided, s3ranger lets boto3 resolve credentials using its [standard credential chain](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html), which includes environment variables, AWS config files, IAM roles, etc.

CLI arguments always override config file settings.

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

| Option                    | Description                            | Example                                                            |
| ------------------------- | -------------------------------------- | ------------------------------------------------------------------ |
| `--endpoint-url`          | Custom S3 endpoint URL                 | `--endpoint-url https://minio.example.com`                         |
| `--region-name`           | AWS region name                        | `--region-name us-west-2`                                          |
| `--profile-name`          | AWS profile name                       | `--profile-name production`                                        |
| `--aws-access-key-id`     | AWS access key ID (CLI only)           | `--aws-access-key-id AKIAIOSFODNN7EXAMPLE`                         |
| `--aws-secret-access-key` | AWS secret access key (CLI only)       | `--aws-secret-access-key wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `--aws-session-token`     | AWS session token (CLI only, optional) | `--aws-session-token token123`                                     |
| `--theme`                 | UI theme                               | `--theme "github dark"`                                            |
| `--config`                | Configuration file path                | `--config ~/.s3ranger.config`                                      |
| `--download-directory`    | Default download directory             | `--download-directory "/tmp"`                                        |
| `--enable-pagination`     | Enable pagination (default)            | `--enable-pagination`                                              |
| `--disable-pagination`    | Disable pagination                     | `--disable-pagination`                                             |

### Keyboard Shortcuts

| Key      | Action                                         |
| -------- | ---------------------------------------------- |
| `Tab`    | Switch between panels                          |
| `Enter`  | Enter bucket/folder or download file           |
| `Space`  | Toggle selection of file/folder                |
| `Ctrl+a` | Select all files/folders in the current prefix |
| `Esc`    | Deselect all selections                        |
| `Ctrl+r` | Refresh current view                           |
| `Ctrl+f` | Filter/search                                  |
| `Ctrl+s` | Sort objects (by name, type, date, size)       |
| `Ctrl+h` | Show help modal                                |
| `Ctrl+q` | Quit application                               |
| `Ctrl+p` | Open command palette                           |
| `u`      | Upload file/folder                             |
| `d`      | Download selected item                         |
| `c`      | Copy selected item(s)                          |
| `m`      | Move selected item(s)                          |
| `Delete` | Delete selected item                           |
| `Ctrl+k` | Rename selected item                           |
| `F1`     | Help                                           |

### Working with S3-Compatible Services

s3ranger works with any S3-compatible service. You can configure these services either via CLI arguments or through AWS config files.

#### LocalStack

LocalStack is a fully functional local AWS cloud stack for testing and development.

**Quick start (CLI):**

```bash
s3ranger --endpoint-url http://localhost:4566 --region-name us-east-1
```

**Using AWS config files:**

Add a LocalStack profile to your `~/.aws/credentials`:

```ini
[localstack]
aws_access_key_id = test
aws_secret_access_key = test
```

Add the endpoint configuration to your `~/.aws/config`:

```ini
[profile localstack]
region = us-east-1
output = json
endpoint_url = http://localhost:4566
```

Then launch s3ranger with the profile:

```bash
s3ranger --profile-name localstack
```

---

#### MinIO

MinIO is a high-performance object storage server compatible with Amazon S3.

> **Note:** For MinIO, the `--aws-access-key-id` corresponds to your MinIO **username** and `--aws-secret-access-key` corresponds to your MinIO **password**. The default credentials for MinIO are `minioadmin` / `minioadmin`.

**Quick start (CLI):**

```bash
s3ranger --endpoint-url http://localhost:9000 --region-name us-east-1 \
         --aws-access-key-id minioadmin \
         --aws-secret-access-key minioadmin
```

**Using AWS config files:**

Add a MinIO profile to your `~/.aws/credentials`:

```ini
[minio]
aws_access_key_id = minioadmin
aws_secret_access_key = minioadmin
```

Add the endpoint configuration to your `~/.aws/config`:

```ini
[profile minio]
region = us-east-1
output = json
endpoint_url = http://localhost:9000
```

Then launch s3ranger with the profile:

```bash
s3ranger --profile-name minio
```

Or set it as default in your s3ranger config (`~/.s3ranger.config`):

```toml
profile_name = "minio"
```

## Configuration

### Configuration File

s3ranger can be configured using a TOML configuration file located at `~/.s3ranger.config`:

```toml
# AWS Configuration
profile_name = "default"

# UI Configuration
theme = "Github Dark"

# Download Configuration
# Default directory for downloads (defaults to ~/Downloads/)
download_directory = "~/Documents/"

# Performance
# Set to false to load all items at once instead of using pagination
enable_pagination = true
```

**Supported config file options:**

- `profile_name` - AWS profile to use (can be overridden with `--profile-name`)
- `theme` - UI theme (Github Dark, Dracula, Solarized, Sepia)
- `download_directory` - Default directory for downloads (defaults to `~/Downloads/`)
- `enable_pagination` - Enable or disable pagination

> **Tip:** Set `download_directory = "."` in your config file to always use the current working directory as the default download location. This is useful when you want downloads to go to your project directory.

> **Note:** AWS credentials (`aws_access_key_id`, `aws_secret_access_key`, `aws_session_token`) are only supported via CLI arguments.

### Interactive Configuration

Run the configuration wizard to set up your config file:

```bash
s3ranger configure
```

## Pagination

s3ranger uses lazy loading with pagination to handle large numbers of buckets and objects efficiently:

- **Bucket list**: Loads 250 buckets at a time
- **Object list**: Loads 25 objects at a time

As you scroll down using the mouse or arrow keys, more items are automatically loaded. This ensures fast initial load times even when you have hundreds of buckets or thousands of objects.

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

- [Report bugs](https://github.com/Sharashchandra/s3ranger/issues)
- [Request features](https://github.com/Sharashchandra/s3ranger/issues)
- [Discussions](https://github.com/Sharashchandra/s3ranger/discussions)
