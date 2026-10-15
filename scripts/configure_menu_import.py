"""Enable the menu-only integration key in an existing private environment.

Never prints the key, changes existing credentials, or replaces an existing key.
Restart the application after running this script.
"""
import argparse
from pathlib import Path
import secrets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env', type=Path, default=Path(__file__).resolve().parents[1] / '.env.demo')
    args = parser.parse_args()
    text = args.env.read_text(encoding='utf-8')
    lines = text.splitlines()
    positions = [i for i, line in enumerate(lines) if line.split('=', 1)[0].strip() == 'MENU_IMPORT_API_KEY']
    if len(positions) > 1:
        raise SystemExit('Duplicate MENU_IMPORT_API_KEY entries; resolve them before continuing.')
    if positions and lines[positions[0]].split('=', 1)[1].strip():
        raise SystemExit('An import key is already configured and was preserved.')
    setting = 'MENU_IMPORT_API_KEY=' + secrets.token_urlsafe(48)
    if positions:
        lines[positions[0]] = setting
    else:
        lines.append(setting)
    args.env.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('Menu import key configured in the private environment. Restart the app. The key was not displayed.')


if __name__ == '__main__':
    main()
