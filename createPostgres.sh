#!/usr/bin/env bash
# exit on error
set -o errexit

# Function to show usage
usage() {
    echo "Usage: $0 -u <username> -p <password> -d <database_name>"
    exit 1
}

# Check if arguments are provided
if [ "$#" -ne 6 ]; then
    usage
fi

# Parse arguments
while getopts ":u:p:d:" opt; do
    case $opt in
        u) USER="$OPTARG"
        ;;
        p) PASSWORD="$OPTARG"
        ;;
        d) DB_NAME="$OPTARG"
        ;;
        \?) echo "Invalid option -$OPTARG" >&2
            usage
        ;;
    esac
done

# Check that arguments are not empty
if [[ -z "$USER" || -z "$PASSWORD" || -z "$DB_NAME" ]]; then
    usage
fi

# Detect operating system
OS=$(uname | tr '[:upper:]' '[:lower:]')

# Function to adjust paths for Docker
adjust_path_for_docker() {
    local path="$1"
    if [[ "$OS" == "mingw"* || "$OS" == "cygwin"* || "$OS" == "windows"* ]]; then
        # Convert Unix-style path to Windows-style for Docker on Windows
        echo "/$(pwd | sed 's|^/c|c:|' | sed 's|/|\\|g')/$path"
    else
        # Use Unix-style path for Linux/MacOS
        echo "$(pwd)/$path"
    fi
}

# Check if PostgreSQL container already exists
if docker ps -a --format '{{.Names}}' | grep -q "^postgres_container\$"; then
    echo "PostgreSQL container already exists. Starting the container..."
    docker start postgres_container
else
    # Pull PostgreSQL image
    echo "Pulling PostgreSQL image..."
    docker pull postgres:latest

    # Create and run the PostgreSQL container
    echo "Creating and running PostgreSQL container..."
    docker run -d \
        --name postgres_container \
        -e POSTGRES_DB="$DB_NAME" \
        -e POSTGRES_USER="$USER" \
        -e POSTGRES_PASSWORD="$PASSWORD" \
        -p 5432:5432 \
        postgres:latest
fi

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to initialize..."
sleep 10  # Asegúrate de que PostgreSQL tenga tiempo para arrancar

# Create PgBouncer configuration files in the current directory (PWD)
echo "Creating PgBouncer configuration files..."
cat > "./pgbouncer.ini" <<EOF
[databases]
$DB_NAME = host=postgres_container port=5432 dbname=$DB_NAME user=$USER password=$PASSWORD

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 100
default_pool_size = 20
log_connections = 1
log_disconnections = 1
log_pooler_errors = 1
EOF

# Correctly generate userlist.txt for PgBouncer
echo "Generating userlist.txt..."
PASSWORD_HASH=$(echo -n "$PASSWORD$USER" | md5sum | awk '{print $1}')  # Generate MD5 hash of PASSWORD + USER
cat > "./userlist.txt" <<EOF
"$USER" "md5$PASSWORD_HASH"
EOF

# Adjust paths for Docker
PGB_INI_PATH=$(adjust_path_for_docker "pgbouncer.ini")
USERLIST_PATH=$(adjust_path_for_docker "userlist.txt")

# Check if PgBouncer container already exists
if docker ps -a --format '{{.Names}}' | grep -q "^pgbouncer_container\$"; then
    echo "PgBouncer container already exists. Starting the container..."
    docker start pgbouncer_container
else
    # Pull PgBouncer image
    echo "Pulling PgBouncer image..."
    docker pull edoburu/pgbouncer:latest

    # Create and run the PgBouncer container
    echo "Creating and running PgBouncer container..."
    docker run -d \
        --name pgbouncer_container \
        --link postgres_container:postgres_container \
        -p 6432:6432 \
        -v "$PGB_INI_PATH:/etc/pgbouncer/pgbouncer.ini" \
        -v "$USERLIST_PATH:/etc/pgbouncer/userlist.txt" \
        -e DB_HOST=postgres_container \
        edoburu/pgbouncer:latest
fi

# Print connection string
echo "PostgreSQL and PgBouncer are running. Connection string:"
echo "postgres://$USER:$PASSWORD@localhost:6432/$DB_NAME"
