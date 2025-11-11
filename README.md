# S3 Handler API

A FastAPI application that provides API services for uploading and downloading files to and from AWS S3 buckets. The application supports both direct upload/download and presigned URL approaches, with built-in multipart upload handling for large files.

## Description

This application acts as a backend service to assist other applications in handling file operations with AWS S3. It provides:

- **Direct Upload/Download**: Upload and download files directly through the FastAPI endpoints
- **Presigned URL Support**: Generate presigned URLs for upload/download operations
- **Multipart Upload**: Automatic multipart upload for large files with configurable chunk sizes
- **Resume Capability**: Handle interrupted uploads and resume operations
- **Retry Logic**: Automatic retry with exponential backoff for failed operations
- **Timeout Handling**: Configurable timeouts for S3 operations
- **Error Handling**: Comprehensive error handling with clear user feedback
- **JSON Exceptions**: All errors returned as JSON responses

## Application Structure

```
s3-handler/
├── app/
│   ├── __init__.py
│   ├── config.py              # Application configuration and settings
│   ├── models.py              # Pydantic models for requests/responses
│   ├── routers/
│   │   ├── __init__.py
│   │   └── s3_routes.py      # S3 API routes
│   └── services/
│       ├── __init__.py
│       └── s3_service.py     # S3 business logic
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # Pytest fixtures
│   ├── test_s3_service.py    # S3 service tests
│   └── test_s3_routes.py     # API route tests
├── main.py                    # FastAPI application entry point
├── pyproject.toml            # Project dependencies
├── pytest.ini                # Pytest configuration
├── Dockerfile                # Docker configuration
├── env.template              # Environment variables template
└── README.md                 # This file
```

## API Routes

### Access Token Generation

- **POST /access-token**: Generate JWT access token for direct upload/download operations
  - Parameters: `s3_region` (query parameter), `s3_bucket` (query parameter)
  - Returns: `{"token": "jwt_token"}`
  - Token expires in configurable minutes (default: 10 minutes, set via `JWT_EXPIRATION_MINUTES` in `.env`)
  - Use Case: Generate token before using direct upload/download endpoints

### Direct Upload/Download

- **POST /upload**: Upload a file directly to S3
  - Parameters: `file` (multipart form data), `key` (query parameter), `token` (query parameter - JWT token)
  - Returns: Upload confirmation with key and bucket
  - Features: Automatic multipart upload for files > 50MB
  - Security: Requires valid JWT token obtained from `/access-token` endpoint

- **GET /download/{key}**: Download a file directly from S3
  - Parameters: `key` (path parameter), `token` (query parameter - JWT token)
  - Returns: File content as stream
  - Example: `/download/my-folder/file.txt?token=your_jwt_token`
  - Security: Requires valid JWT token obtained from `/access-token` endpoint

### Presigned URL Operations

- **POST /presigned/upload**: Generate presigned URL for uploading
  - Parameters: `key` (query parameter), `s3_region` (query parameter), `s3_bucket` (query parameter), `content_type` (optional, query parameter)
  - Returns: Presigned upload URL with expiration time (60 minutes default)
  - Use Case: Frontend uploads directly to S3
  - Example: `/presigned/upload?key=my-file.txt&s3_region=us-east-1&s3_bucket=my-bucket`

- **GET /presigned/download/{key}**: Generate presigned URL for downloading
  - Parameters: `key` (path parameter), `s3_region` (query parameter), `s3_bucket` (query parameter)
  - Returns: Presigned download URL with expiration time (60 minutes default)
  - Example: `/presigned/download/my-folder/file.txt?s3_region=us-east-1&s3_bucket=my-bucket`
  - Use Case: Frontend downloads directly from S3

### Status Check

- **GET /status**: Check upload status of a file
  - Parameters: `key` (query parameter), `s3_region` (query parameter), `s3_bucket` (query parameter)
  - Returns: File existence, size, last modified time, and etag
  - Example: `/status?key=my-folder/file.txt&s3_region=us-east-1&s3_bucket=my-bucket`

### Health Check

- **GET /health**: Health check endpoint
- **GET /**: Application information and API documentation links

## Setting Up

### Prerequisites

- Python 3.13 or higher
- uv package manager
- AWS account with S3 access
- AWS credentials

### Installing uv Package Manager

If you don't have uv installed:

```bash
# On Linux and macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or using pip
pip install uv
```

### Setting Up Environment Variables

1. Copy the environment template:
```bash
cp env.template .env
```

2. Edit `.env` file and add your configuration:

**For explicit AWS credentials:**
```env
AWS_ACCESS_KEY_ID=your_access_key_id
AWS_SECRET_ACCESS_KEY=your_secret_access_key
SECRET=your_jwt_secret_key
JWT_EXPIRATION_MINUTES=10
```

**For IAM Role (EC2 instances):**
```env
# Leave AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY empty or unset
# The application will use IAM role credentials automatically
SECRET=your_jwt_secret_key
JWT_EXPIRATION_MINUTES=10
```

3. Ensure proper AWS permissions:
   - **If using explicit credentials**: Your IAM user needs the following S3 permissions:
     - `s3:PutObject`
     - `s3:GetObject`
     - `s3:DeleteObject` (for cleanup operations)
     - `s3:ListBucket` (optional, for bucket operations)
   - **If using IAM Role (EC2)**: The EC2 instance's IAM role needs the same S3 permissions listed above

## Running the Application

### Run Locally with uv

1. Install dependencies:
```bash
uv sync
```

2. Run the application:
```bash
uv run main.py
```

The application will start on `http://0.0.0.0:8000`

3. Access the API documentation:
   - Swagger UI: `http://localhost:8000/docs`
   - ReDoc: `http://localhost:8000/redoc`

### Run with Docker

1. Build the Docker image:
```bash
docker build -t s3handler .
```

2. Run the container:
```bash
docker run --name s3handlerapi -p 8000:8000 --env-file .env s3handler
```

The application will start on `http://localhost:8000`

### Run Tests
install necessary extra group "test" for testing
```bash
uv sync --extra test
```

#### Run all tests:
```bash
uv run pytest
```

#### Run with verbose output:
```bash
uv run pytest -v
```

#### Run specific test file:
```bash
uv run pytest tests/test_s3_service.py -v
uv run pytest tests/test_s3_routes.py -v
```

## Configuration

The application can be configured through environment variables:

- **AWS Configuration**:
  - `AWS_ACCESS_KEY_ID`: AWS access key (optional - if not provided, will use IAM role)
  - `AWS_SECRET_ACCESS_KEY`: AWS secret key (optional - if not provided, will use IAM role)
  
  **Authentication Methods:**
  - **Option 1: Explicit Credentials**: Set `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in environment variables
  - **Option 2: IAM Role** (recommended for EC2): Leave credentials unset/empty, and the application will automatically use IAM role credentials from EC2 instance metadata service

- **JWT Configuration**:
  - `SECRET`: Secret key for JWT token signing (required)
  - `JWT_EXPIRATION_MINUTES`: Token expiration time in minutes (default: 10 minutes)

- **Multipart Upload** (configurable in code):
  - `multipart_chunk_size_mb`: Chunk size in MB (default: 50MB)
  - `max_part_number`: Maximum number of parts (default: 10000)

- **Presigned URL** (configurable in code):
  - `presigned_url_expiration_minutes`: URL expiration time (default: 60 minutes)

- **Retry Configuration** (configurable in code):
  - `max_retries`: Maximum retry attempts (default: 3)
  - `retry_delay_seconds`: Initial retry delay (default: 2 seconds)

- **Timeout Configuration** (configurable in code):
  - `upload_timeout_seconds`: Upload operation timeout (default: 300 seconds)
  - `download_timeout_seconds`: Download operation timeout (default: 300 seconds)

## Features

### Multipart Upload
- Automatically uses multipart upload for files larger than the configured chunk size
- Configurable chunk size (default: 50MB)
- Supports resuming interrupted uploads
- Handles cleanup of failed multipart uploads

### Retry Logic
- Exponential backoff for failed operations
- Configurable retry attempts
- Automatic cleanup of failed uploads

### Error Handling
- Comprehensive error messages
- JSON exception responses
- Proper logging for debugging
- User-friendly error messages

### Timeout Handling
- Configurable timeouts for S3 operations
- Prevents hanging operations
- Graceful error handling on timeout

## Usage Examples

### Generate Access Token
First, generate a JWT token for direct upload/download operations:
```bash
curl -X POST "http://localhost:8000/access-token?s3_region=us-east-1&s3_bucket=my-bucket"
```

Response:
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### Direct Upload
```bash
# First get a token
TOKEN=$(curl -s -X POST "http://localhost:8000/access-token?s3_region=us-east-1&s3_bucket=my-bucket" | jq -r '.token')

# Then upload the file
curl -X POST "http://localhost:8000/upload?key=my-folder/file.txt&token=$TOKEN" \
  -F "file=@local-file.txt"
```

### Direct Download
```bash
# First get a token
TOKEN=$(curl -s -X POST "http://localhost:8000/access-token?s3_region=us-east-1&s3_bucket=my-bucket" | jq -r '.token')

# Then download the file
curl -X GET "http://localhost:8000/download/my-folder/file.txt?token=$TOKEN" \
  --output downloaded-file.txt
```

### Get Presigned Upload URL
```bash
curl -X POST "http://localhost:8000/presigned/upload?key=my-folder/file.txt&s3_region=us-east-1&s3_bucket=my-bucket&content_type=text/plain"
```

### Get Presigned Download URL
```bash
curl -X GET "http://localhost:8000/presigned/download/my-folder/file.txt?s3_region=us-east-1&s3_bucket=my-bucket"
```

### Check Upload Status
```bash
curl -X GET "http://localhost:8000/status?key=my-folder/file.txt&s3_region=us-east-1&s3_bucket=my-bucket"
```

## Testing

The application includes comprehensive test coverage:

- **Unit Tests**: Test individual service methods
- **Integration Tests**: Test API endpoints with mocked S3 operations
- **Mocking**: Uses pytest fixtures and mocks for isolated testing

Run tests:
```bash
uv sync --extra test
uv run pytest
```

## Technologies Used

- **FastAPI**: Modern, fast web framework for building APIs
- **aioboto3**: Async AWS SDK for Python
- **Pydantic**: Data validation and settings management
- **uv**: Fast Python package manager and project manager
- **pytest**: Testing framework

## License

This project is open source and available for use.

