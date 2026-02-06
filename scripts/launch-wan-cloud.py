#!/usr/bin/env python3
"""
Launch Wan2.2-Animate Cloud Service
Opens the official HuggingFace Gradio space (recommended for 16GB VRAM GPUs)
"""

import webbrowser
import sys

HUGGINGFACE_SPACE = "https://huggingface.co/spaces/Wan-AI/Wan2.2-Animate"
MODELSCOPE_SPACE = "https://www.modelscope.cn/studios/Wan-AI/Wan2.2-Animate"

def main():
    print("=" * 60)
    print("🎬 Wan2.2-Animate-14B Cloud Launcher")
    print("=" * 60)
    print()
    print("This will open the official Gradio space in your browser.")
    print("The cloud service runs on powerful GPUs and is FREE to use.")
    print()
    print("Benefits:")
    print("  ✅ No local installation required")
    print("  ✅ Faster processing (H100/A100 GPUs)")
    print("  ✅ No VRAM limitations")
    print("  ✅ Higher resolution support")
    print()
    print("Available options:")
    print("  1. HuggingFace Space (Recommended)")
    print("  2. ModelScope Space (Alternative)")
    print("  3. Exit")
    print()

    while True:
        try:
            choice = input("Select option [1-3]: ").strip()

            if choice == "1":
                print(f"\n🌐 Opening HuggingFace Space...")
                print(f"   {HUGGINGFACE_SPACE}")
                webbrowser.open(HUGGINGFACE_SPACE)
                print("\n✓ Browser opened successfully!")
                print("📝 Note: If you see a queue, please wait. The service is free and shared.")
                break

            elif choice == "2":
                print(f"\n🌐 Opening ModelScope Space...")
                print(f"   {MODELSCOPE_SPACE}")
                webbrowser.open(MODELSCOPE_SPACE)
                print("\n✓ Browser opened successfully!")
                break

            elif choice == "3":
                print("\n👋 Goodbye!")
                sys.exit(0)

            else:
                print("❌ Invalid choice. Please enter 1, 2, or 3.")

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            sys.exit(0)

    print()
    print("=" * 60)
    print("🎉 Enjoy creating amazing character animations!")
    print("=" * 60)

if __name__ == "__main__":
    main()
