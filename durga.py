import os
import sys
import subprocess

def clear_cache():
    print("Clearing cache...")
    # Find and remove __pycache__ directories
    for root, dirs, files in os.walk('.'):
        if '__pycache__' in dirs:
            pycache_dir = os.path.join(root, '__pycache__')
            print(f"Removing {pycache_dir}")
            try:
                subprocess.run(['rm', '-rf', pycache_dir], check=True)
            except Exception as e:
                print(f"Error removing {pycache_dir}: {e}")

def run_server():
    print("Starting development server...")
    try:
        subprocess.run([sys.executable, 'manage.py', 'runserver', '0.0.0.0:8000'], check=True)
    except KeyboardInterrupt:
        print("\nServer stopped.")
    except Exception as e:
        print(f"Error starting server: {e}")

def main():
    clear_cache()
    run_server()

if __name__ == '__main__':
    main()
