import sys
from phonexr_bridge.setup_ui import main

if __name__ == '__main__':
    if '--help' in sys.argv:
        print('PhoneXR Companion: graphical pairing and input controls. No arguments required.')
    else:
        main(smoke_test='--self-test' in sys.argv)
