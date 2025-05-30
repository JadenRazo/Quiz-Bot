# Quiz Bot Autostart Script
# This script starts the quiz bot in a tmux session

# Configuration
BOT_DIR="/quiz_bot"
VENV_PATH="bot-env/bin/activate"
SESSION_NAME="quiz_bot"
LOG_FILE="$BOT_DIR/bot_startup.log"

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Create log directory if it doesn't exist
mkdir -p $(dirname "$LOG_FILE")
log "Starting Quiz Bot autostart script"

# Check if tmux is installed
if ! command -v tmux &> /dev/null; then
    log "ERROR: tmux is not installed. Please install it with: apt-get install tmux"
    exit 1
fi

# Check if the bot directory exists
if [ ! -d "$BOT_DIR" ]; then
    log "ERROR: Bot directory $BOT_DIR does not exist"
    exit 1
fi

# Check if the virtualenv activation script exists
if [ ! -f "$BOT_DIR/$VENV_PATH" ]; then
    log "WARNING: Virtual environment activation script not found at $BOT_DIR/$VENV_PATH"
    log "Will try to proceed anyway, as the script might be located elsewhere"
fi

# Function to start the bot in tmux
start_bot() {
    # Check if the session already exists
    if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
        log "Session $SESSION_NAME already exists, attaching..."
        tmux attach-session -t "$SESSION_NAME"
        return
    fi

    # Create a new tmux session
    log "Creating new tmux session: $SESSION_NAME"
    tmux new-session -d -s "$SESSION_NAME"

    # Setup the window
    tmux send-keys -t "$SESSION_NAME" "cd $BOT_DIR" C-m
    log "Changed directory to $BOT_DIR"

    # Activate virtual environment
    tmux send-keys -t "$SESSION_NAME" "source bot-env/bin/activate" C-m
    log "Activated virtual environment with: source bot-env/bin/activate"

    # Run the bot
    log "Starting the bot..."
    tmux send-keys -t "$SESSION_NAME" "python3 main.py" C-m

    # Attach to the session
    log "Attaching to tmux session..."
    tmux attach-session -t "$SESSION_NAME"
}

# Function to check if the bot is already running
check_bot_running() {
    if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
        log "Bot appears to be already running in tmux session: $SESSION_NAME"
        read -p "Do you want to (a)ttach to the existing session, (r)estart it, or (c)ancel? [a/r/c]: " choice
        case "$choice" in
            a|A) 
                tmux attach-session -t "$SESSION_NAME"
                exit 0
                ;;
            r|R)
                log "Killing existing session and starting fresh..."
                tmux kill-session -t "$SESSION_NAME"
                # Continue to start_bot
                ;;
            *)
                log "Operation cancelled by user"
                exit 0
                ;;
        esac
    fi
}

# Main execution
check_bot_running
start_bot

exit 0 