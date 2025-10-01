#!/usr/bin/env python3
"""
Standalone pipeline runner for Google App Engine
This should be run as a separate Cloud Run service or Compute Engine instance
GAE Standard does not support long-running WebSocket connections
"""

if __name__ == "__main__":
    from pipeline1 import main
    main()
