#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hell World Script
A playful twist on the classic "Hello World" program.
"""

def main():
    """Print a hellish greeting to the world."""
    print("HELL WORLD!")
    print("\n" + "=" * 40)
    print("Welcome to the fiery depths of Python!")
    print("=" * 40)
    
    # Additional hellish features
    temperature = 666
    print(f"\nCurrent temperature: {temperature}C")
    print("Warning: It's getting hot in here!")
    
    # Demon list (because why not)
    demons = ["Beelzebub", "Lucifer", "Asmodeus", "Belphegor"]
    print(f"\nDemons on duty today: {', '.join(demons)}")
    
    # Countdown to doom
    print("\nCountdown to doom:")
    for i in range(3, 0, -1):
        print(f"{i}...")
    
    print("\nJust kidding! Have a nice day!")

if __name__ == "__main__":
    main()