#!/bin/bash

# Load environment variables from .env file
if [ -f .env ]; then
    set -a  # automatically export all variables
    source .env
    set +a  # turn off automatic export
    echo "Loaded environment variables from .env"
else
    echo "Warning: .env file not found"
fi

# Batch script to run label_llm.py 5 times with different run names
# Each run uses the format: gemini-2.5-pro-pass-$VAR where $VAR goes from 1 to 5

echo "Starting batch labeling with 5 runs..."
echo "=================================="

for i in {3..5}; do
    run_name="gemini-2.5-pro-pass-$i"
    echo "Starting run $i of 5: $run_name"
    echo "Time: $(date)"
    
    # Run the labeling script with the current run name in background
    python label_llm.py --model-name gemini-2.5-pro --run-name "$run_name" &
    python_pid=$!

    echo "Python process started with PID: $python_pid"
    
    # Wait for the Python process to complete
    while kill -0 $python_pid 2>/dev/null; do
        echo "Process $python_pid is still running... (checked at $(date))"
        sleep 60  # Check every minute
    done
    
    # Check the exit status
    wait $python_pid
    exit_status=$?
    
    if [ $exit_status -eq 0 ]; then
        echo "Run $i completed successfully: $run_name"
    else
        echo "Run $i failed with exit code $exit_status: $run_name"
    fi
    
    echo "=================================="
done

echo "All 5 runs completed!"
echo "Final time: $(date)"
