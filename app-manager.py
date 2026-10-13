#!/usr/bin/env python3
"""Installed Apps — list and uninstall software on Ubuntu (APT, Snap, Flatpak, Lutris, manual installs)."""
import os
import re
import glob
import json
import shlex
import shutil
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk
try:
    gi.require_version('GioUnix', '2.0')
    from gi.repository import GioUnix
    DesktopAppInfo = GioUnix.DesktopAppInfo
except (ImportError, ValueError):
    DesktopAppInfo = Gio.DesktopAppInfo

APP_ID = 'io.github.vlgn.AppManager'
SETTINGS_FILE = os.path.join(os.path.expanduser('~'), '.config', 'app-manager', 'settings.json')

# ---------- перевод: ключи — русские строки, EN — английский перевод
EN = {
    'Установленные программы': 'Installed Apps',
    'Вручную': 'Manual', 'Защищено': 'Protected', 'Системное': 'System', 'Обычное': 'Regular', 'Ярлык': 'Shortcut',
    'Игра Lutris': 'Lutris game', 'Файлы игры и Wine-префикс': 'Game files and Wine prefix',
    'Настройки игры в Lutris': 'Game settings in Lutris', 'Обложка': 'Cover art',
    'Запись в библиотеке Lutris': 'Lutris library entry', 'Ярлык в меню': 'Menu shortcut', 'Значок': 'Icon',
    'Значки ({n} шт.)': 'Icons ({n} files)', 'Папка программы': 'Program folder',
    'Исполняемый файл': 'Executable', 'Фоновая служба (будет остановлена)': 'Background service (will be stopped)',
    'Автозапуск': 'Autostart entry', 'Данные и настройки': 'Data and settings',
    'Завершён процесс {pid}: {name}\n': 'Terminated process {pid}: {name}\n',
    'Останавливаю службу {unit}\n': 'Stopping service {unit}\n',
    'Игра удалена из библиотеки Lutris\n': 'Game removed from the Lutris library\n',
    'Ошибка базы Lutris: {err}\n': 'Lutris database error: {err}\n',
    'Пропущено (небезопасный путь): {path}\n': 'Skipped (unsafe path): {path}\n',
    'Удалено: {path}\n': 'Removed: {path}\n', 'Ошибка: {path}: {err}\n': 'Error: {path}: {err}\n',
    'Среда выполнения': 'Runtime', 'Приложения': 'Applications', 'Все пакеты': 'All packages',
    'Обновить список': 'Refresh', 'Разрешить удаление защищённых (опасно)': 'Allow removing protected (dangerous)',
    'Язык': 'Language', 'Как в системе': 'System default',
    'Поиск по названию или пакету…': 'Search by name or package…', 'Все источники': 'All sources',
    'Любой тип': 'Any type', 'Обычные': 'Regular', 'Системные': 'System', 'Защищённые': 'Protected',
    'Только установленные вручную': 'Manually installed only', 'Пакет': 'Package', 'Источник': 'Source',
    'Версия': 'Version', 'Размер': 'Size', 'Тип': 'Type', 'Название': 'Name',
    'Собираю список программ…': 'Collecting installed software…', 'Ничего не найдено': 'Nothing found',
    'Измените запрос или фильтры': 'Try a different search or filters', 'Удалить': 'Uninstall',
    'Нужно для работы системы — удаление может её сломать': 'Required by the system — removing it may break it',
    'Входит в стандартную установку Ubuntu — удалять можно, но осторожно':
        'Part of the standard Ubuntu install — can be removed, but be careful',
    'Установлено вами — можно спокойно удалять': 'Installed by you — safe to remove',
    'Ярлык программы, установленной не через пакетный менеджер': 'Shortcut of an app installed outside the package manager',
    'Диск': 'Disk', 'Домашний диск': 'Home disk',
    '{name}: занято {used} из {total}  •  свободно {free}': '{name}: {used} of {total} used  •  {free} free',
    '{mount}: занято {pct}': '{mount}: {pct} used',
    'Показано: {n}   •   Занимают: {size}': 'Shown: {n}   •   Total size: {size}',
    'Программа установлена вне домашней папки и не через пакет — удалить отсюда нельзя':
        'Installed outside your home folder and not as a package — cannot be removed here',
    'Защищённый компонент: от него зависит работа системы. Разблокировать можно в меню ☰ (опасно).':
        'Protected component: the system depends on it. You can unlock it in the ☰ menu (dangerous).',
    'Удалить «{name}»': 'Uninstall “{name}”',
    'Удаление защищённых пакетов разрешено. Будьте осторожны!': 'Removing protected packages is allowed. Be careful!',
    'Будет удалён snap-пакет «{pkg}».': 'The snap “{pkg}” will be removed.',
    'Будет удалён flatpak «{pkg}».': 'The flatpak “{pkg}” will be removed.',
    'Удалить также данные приложения': 'Also delete app data',
    'Не удалось подготовить удаление: {err}': 'Could not prepare removal: {err}', 'нечего удалять': 'nothing to remove',
    'Удаление заблокировано': 'Removal blocked',
    'Вместе с «{name}» будут удалены защищённые системные пакеты ({n}), без которых Ubuntu может не загрузиться '
    'или потерять рабочий стол:\n\n{list}\n\nЕсли вы точно знаете, что делаете, включите в меню ☰ '
    '«Разрешить удаление защищённых».':
        'Removing “{name}” would also remove protected system packages ({n}) that Ubuntu needs to boot or show '
        'the desktop:\n\n{list}\n\nIf you really know what you are doing, enable “Allow removing protected” '
        'in the ☰ menu.',
    'Понятно': 'OK', 'Будут удалены пакеты ({n}):': 'These packages will be removed ({n}):',
    '⚠ ОПАСНО: будут удалены защищённые системные пакеты ({list}). Система может перестать работать!\n\n':
        '⚠ DANGER: protected system packages will be removed ({list}). The system may stop working!\n\n',
    'Внимание: будут удалены компоненты стандартной установки Ubuntu ({list}).\n\n':
        'Note: parts of the standard Ubuntu install will be removed ({list}).\n\n',
    'Удалить также настройки (purge)': 'Also delete settings (purge)',
    'Не нашёл файлов программы для удаления': 'No program files found to remove',
    'Игра установлена через Lutris.': 'This game was installed with Lutris.',
    'Программа установлена вручную, не через пакетный менеджер.': 'This app was installed manually, not with a package manager.',
    ' Будут удалены отмеченные пункты (без возможности восстановления):':
        ' The checked items will be permanently deleted:',
    '⚠ Lutris сейчас запущен — закройте его перед удалением.\n\n': '⚠ Lutris is running — close it before uninstalling.\n\n',
    'Удалить «{name}»?': 'Uninstall “{name}”?', 'Отмена': 'Cancel', 'Программа': 'Program',
    'Данные и настройки (оставьте, если планируете переустановить)': 'Data and settings (keep them if you plan to reinstall)',
    '⚠ ОПАСНО: это защищённый системный компонент. Система может перестать работать!\n\n':
        '⚠ DANGER: this is a protected system component. The system may stop working!\n\n',
    'Внимание: это часть стандартной установки системы.\n\n': 'Note: this is part of the standard system install.\n\n',
    'Закрыть': 'Close', 'Удаление «{name}»': 'Uninstalling “{name}”', '\n✔ Готово.\n': '\n✔ Done.\n',
    '«{name}» удалено': '“{name}” uninstalled', '\nОтменено: пароль не введён.\n': '\nCancelled: no password entered.\n',
    '\n✘ Ошибка (код {code}).\n': '\n✘ Failed (code {code}).\n',
    'также используется: {names}': 'also used by: {names}',
    'Также будут установлены или обновлены пакеты ({n}): {list}\n\n':
        'These packages will also be installed or upgraded ({n}): {list}\n\n',
    'Принудительно завершён процесс {pid}\n': 'Killed process {pid}\n',
}


def load_settings():
    try:
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(data):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(data, f)


def detect_language(choice):
    if choice in ('ru', 'en'):
        return choice
    langs = [l.split('_')[0].split('.')[0] for l in GLib.get_language_names()]
    return 'ru' if langs and langs[0] == 'ru' else 'en'


ORIG_LANGUAGE = os.environ.get('LANGUAGE')


def apply_language(choice):
    """Устанавливает язык интерфейса и язык названий программ из .desktop-файлов."""
    global LANG
    if ORIG_LANGUAGE is None:
        os.environ.pop('LANGUAGE', None)
    else:
        os.environ['LANGUAGE'] = ORIG_LANGUAGE
    LANG = detect_language(choice)
    if choice != 'auto':
        os.environ['LANGUAGE'] = 'ru_RU:ru' if LANG == 'ru' else 'en_US:en'


LANG = 'en'
apply_language(load_settings().get('language', 'auto'))


def tr(text, **kw):
    if LANG == 'en':
        text = EN.get(text, text)
    return text.format(**kw) if kw else text
C_ENV = dict(os.environ, LC_ALL='C', LANG='C', LANGUAGE='C')
SOURCE_LABELS = {'apt': 'APT', 'snap': 'Snap', 'flatpak': 'Flatpak', 'local': 'Вручную', 'lutris': 'Lutris'}

# Уровни: protected — удаление сломает систему; system — часть стандартной установки Ubuntu;
# user — установлено пользователем; shortcut — ярлык без пакета.
LEVEL_LABELS = {'protected': 'Защищено', 'system': 'Системное', 'user': 'Обычное', 'shortcut': 'Ярлык'}
LEVEL_ICONS = {'protected': 'channel-secure-symbolic', 'system': 'emblem-system-symbolic',
               'user': 'avatar-default-symbolic', 'shortcut': 'emblem-symbolic-link'}
LEVEL_CSS = {'protected': 'error', 'system': 'warning'}
LEVEL_ORDER = {'user': 0, 'shortcut': 1, 'system': 2, 'protected': 3}

# Корни «защищённых»: всё, от чего они зависят (Depends/Pre-Depends), тоже защищено.
PROTECTED_ROOTS = {
    'gnome-shell', 'gnome-session', 'gdm3', 'mutter', 'nautilus', 'gnome-control-center',
    'gnome-settings-daemon', 'network-manager', 'systemd', 'systemd-sysv', 'sudo', 'apt', 'dpkg',
    'snapd', 'polkitd', 'pkexec', 'xwayland', 'linux-generic', 'linux-generic-hwe-26.04',
    'grub-efi-amd64-signed', 'grub-pc', 'shim-signed', 'initramfs-tools', 'linux-firmware',
    'pipewire', 'wireplumber', 'dbus', 'ubuntu-minimal', 'ubuntu-desktop-minimal', 'gnome-terminal',
    'ptyxis', 'login', 'passwd', 'adduser', 'ca-certificates', 'netplan.io', 'ubuntu-drivers-common',
}
# Корни «системных»: всё из стандартной установки (включая Recommends).
SYSTEM_ROOTS = {'ubuntu-desktop', 'ubuntu-desktop-minimal', 'ubuntu-standard', 'ubuntu-minimal',
                'ubuntu-server', 'ubuntu-restricted-addons', 'ubuntu-desktop-bootstrap'}
PROTECTED_SNAPS = {'snapd'}
SYSTEM_SNAPS_RE = re.compile(r'^(core\d*|bare|gnome-[\d-]+(-sdk)?|kf[56]-core\d+|mesa-[\w-]+|gtk2?-common-themes|'
                             r'snap-store|snapd-desktop-integration|firmware-updater|desktop-security-center|'
                             r'prompting-client|firefox|thunderbird)$')


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, env=C_ENV).stdout
    except FileNotFoundError:
        return ''


def human_size(n):
    if n is None or n < 0:
        return '—'
    units = ('B', 'KB', 'MB', 'GB') if LANG == 'en' else ('Б', 'КБ', 'МБ', 'ГБ')
    for unit in units:
        if n < 1024 or unit == units[-1]:
            text = f'{n:.0f} {unit}' if unit == units[0] else f'{n:.1f} {unit}'
            return text if LANG == 'en' else text.replace('.', ',')
        n /= 1024


def parse_size(text):
    m = re.match(r'([\d.]+)\s*([kMGT]?)B', text.replace('\xa0', ' '))
    if not m:
        return -1
    mult = {'': 1, 'k': 1e3, 'M': 1e6, 'G': 1e9, 'T': 1e12}[m.group(2)]
    return int(float(m.group(1)) * mult)


class Pkg(GObject.Object):
    __gsignals__ = {'changed': (GObject.SignalFlags.RUN_FIRST, None, ())}  # размер посчитан позже

    def __init__(self, name, pkg, source, version='', size=-1, summary='', icon=None,
                 manual=True, installation='', removable=True, level='user'):
        super().__init__()
        self.name, self.pkg, self.source = name, pkg, source
        self.version, self.size, self.summary = version, size, summary
        self.icon, self.manual, self.installation = icon, manual, installation
        self.removable, self.level = removable, level
        self.extra_files = []   # локальные копии ярлыков, удаляемые вместе с пакетом
        self.local = None       # данные для удаления программ, установленных вручную / через Lutris


def dep_alternatives(field):
    """'a (>= 1) | b, c:any' -> [['a', 'b'], ['c']]"""
    groups = []
    for part in field.split(','):
        alts = [a.strip().split(' ')[0].split(':')[0] for a in part.split('|')]
        alts = [a for a in alts if a]
        if alts:
            groups.append(alts)
    return groups


def classify_debs():
    """Возвращает {имя_пакета: 'protected' | 'system' | 'user'} для установленных deb-пакетов."""
    meta, providers = {}, {}
    out = run(['dpkg-query', '-W', '-f=${Package}\t${db:Status-Abbrev}\t${Essential}\t${Priority}\t'
               '${Pre-Depends}\t${Depends}\t${Recommends}\t${Provides}\n'])
    for line in out.splitlines():
        p = line.split('\t')
        if len(p) < 8 or not p[1].startswith('ii'):
            continue
        name = p[0]
        meta[name] = dict(essential=p[2] == 'yes', priority=p[3],
                          hard=dep_alternatives(p[4] + ',' + p[5]), rec=dep_alternatives(p[6]))
        providers.setdefault(name, set()).add(name)
        for grp in dep_alternatives(p[7]):
            providers.setdefault(grp[0], set()).add(name)

    def resolve(groups, strict):
        """Пакеты, которые нельзя убрать, не нарушив зависимость.
        strict: если зависимость можно удовлетворить несколькими установленными пакетами — ни один не обязателен."""
        res = set()
        for alts in groups:
            cands = set().union(*(providers.get(a, set()) for a in alts))
            if cands and (len(cands) == 1 or not strict):
                res |= cands
        return res

    def closure(roots, with_rec):
        seen, stack = set(), [r for r in roots if r in meta]
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            stack.extend(resolve(meta[n]['hard'], strict=True) - seen)
            if with_rec:
                stack.extend(resolve(meta[n]['rec'], strict=False) - seen)
        return seen

    prot_roots = {n for n, m in meta.items() if m['essential'] or m['priority'] == 'required'
                  or n.startswith(('linux-image-', 'linux-modules-'))}
    protected = closure(prot_roots | PROTECTED_ROOTS, with_rec=False)
    system = closure(SYSTEM_ROOTS | {n for n, m in meta.items() if m['priority'] in ('important', 'standard')},
                     with_rec=True)
    return {n: 'protected' if n in protected else 'system' if n in system else 'user' for n in meta}


def snap_level(name, is_base):
    if name in PROTECTED_SNAPS:
        return 'protected'
    return 'system' if is_base or SYSTEM_SNAPS_RE.match(name) else 'user'


# ---------- программы, установленные не через пакетный менеджер

HOME = os.path.expanduser('~')
LUTRIS_DIR = os.path.join(HOME, '.local/share/lutris')
LUTRIS_FLATPAK_DIR = os.path.join(HOME, '.var/app/net.lutris.Lutris/data/lutris')
INTERPRETERS = re.compile(r'^(python[\d.]*|bash|sh|dash|zsh|perl|ruby|node|java|wine\d*|mono|gjs|electron\d*)$')
# Общие папки, которые никогда не считаются «папкой программы» и не удаляются целиком
COMMON_DIRS = {
    '', '.local', '.local/share', '.local/bin', '.local/lib', '.local/state', '.local/opt', '.config',
    '.cache', '.var', '.var/app', 'snap', 'bin', 'opt', 'Applications', 'Apps', 'AppImages', 'Programs',
    'apps', 'Games', '.local/share/applications', '.local/share/icons', '.config/autostart',
    '.config/systemd', '.config/systemd/user', '.local/share/lutris',
    # общие папки инструментов и пользовательских проектов — целиком никогда не удаляются
    '.cargo', '.cargo/bin', '.rustup', 'go', 'go/bin', '.go', '.npm', '.npm-global', '.nvm', '.pyenv', '.rbenv',
    '.sdkman', '.deno', '.bun', '.conda', '.wine', '.virtualenvs', '.local/share/virtualenvs',
    '.local/share/pipx', '.local/share/pipx/venvs', '.local/share/uv', '.local/share/uv/tools',
    '.local/share/JetBrains', '.local/share/Steam', '.steam', '.local/share/flatpak',
    'Projects', 'projects', 'code', 'Code', 'dev', 'src', 'git', 'repos', 'workspace', 'Development',
}
GENERIC_NAMES = {'app', 'apps', 'bin', 'run', 'start', 'launch', 'launcher', 'main', 'apprun', 'desktop',
                 'client', 'python', 'python3', 'program', 'programs'}
for _d in ('DIRECTORY_DESKTOP', 'DIRECTORY_DOCUMENTS', 'DIRECTORY_DOWNLOAD', 'DIRECTORY_MUSIC',
           'DIRECTORY_PICTURES', 'DIRECTORY_PUBLIC_SHARE', 'DIRECTORY_TEMPLATES', 'DIRECTORY_VIDEOS'):
    _p = GLib.get_user_special_dir(getattr(GLib.UserDirectory, _d))
    if _p and _p.startswith(HOME + '/'):
        COMMON_DIRS.add(os.path.relpath(_p, HOME))
COMMON_DIRS |= {'Desktop', 'Documents', 'Downloads', 'Music', 'Pictures', 'Videos', 'Public', 'Templates'}


def in_home(path):
    return bool(path) and os.path.abspath(path).startswith(HOME + '/')


def safe_to_delete(path):
    path = os.path.abspath(path)
    return in_home(path) and os.path.relpath(path, HOME) not in COMMON_DIRS


def norm_name(text):
    return re.sub(r'[\W_]+', '', text.lower())


def app_keys(names):
    """Нормализованные варианты названий программы: «Foo Bar», foo-bar.sh, org.example.FooBar → foobar."""
    keys = set()
    for n in names:
        if not n:
            continue
        for part in (n, os.path.splitext(n)[0], n.split('.')[-1] if '.' in n else n):
            k = norm_name(part)
            if len(k) >= 3 and k not in GENERIC_NAMES:
                keys.add(k)
    return keys


def install_root(path, keys):
    """Папка программы в $HOME, содержащая path: самая верхняя папка, чьё имя совпадает с названием
    программы (общие папки пропускаются). None — если такой нет, тогда удаляется только сам файл."""
    if not in_home(path):
        return None
    parts = os.path.relpath(os.path.abspath(path), HOME).split('/')
    for i in range(1, len(parts)):
        cand = '/'.join(parts[:i])
        if cand in COMMON_DIRS:
            continue
        d = norm_name(parts[i - 1])
        if len(d) >= 3 and d not in GENERIC_NAMES and any(k in d or d in k for k in keys):
            return os.path.join(HOME, cand)
    return None


def exec_target(app):
    """Исполняемый файл программы из строки Exec (пропуская env, VAR=..., интерпретаторы)."""
    try:
        argv = shlex.split(app.get_commandline() or '')
    except ValueError:
        return None
    argv = [a for a in argv if not a.startswith('%')]
    i = 0
    while i < len(argv) and (argv[i] == 'env' or '=' in argv[i] or argv[i].startswith('-')):
        i += 1
    if i >= len(argv):
        return None
    exe = shutil.which(argv[i]) or argv[i]
    if INTERPRETERS.match(os.path.basename(exe)):
        for arg in argv[i + 1:]:
            if not arg.startswith('-'):
                return os.path.expanduser(arg)
    return exe


def dpkg_owner(path):
    out = run(['dpkg-query', '-S', path])
    for line in out.splitlines():
        if ': ' in line and not line.startswith('diversion'):
            return line.rsplit(': ', 1)[0].split(',')[0].strip()
    return None


def system_desktop_owner(basename):
    for d in GLib.get_system_data_dirs():
        f = os.path.join(d, 'applications', basename)
        if os.path.exists(f):
            owner = dpkg_owner(os.path.realpath(f))
            if owner:
                return owner
    return None


def classify_local(a, fn, name, desc, icon, deb, deb_level):
    """Ярлык не принадлежит пакету: копия ярлыка пакета, игра Lutris или программа в $HOME."""
    cmd = a.get_commandline() or ''
    m = re.search(r'lutris:rungameid/(\d+)', cmd)
    if m:
        flatpak = 'net.lutris.Lutris' in cmd or re.search(r'\bflatpak\b', cmd)
        item = Pkg(name, f'lutris #{m.group(1)}', 'lutris', summary=desc or tr('Игра Lutris'), icon=icon)
        item.local = dict(kind='lutris', game_id=int(m.group(1)), desktop=fn, icon_name=a.get_string('Icon'),
                          lutris_dir=LUTRIS_FLATPAK_DIR if flatpak else LUTRIS_DIR)
        return item

    exe = exec_target(a)
    real = os.path.realpath(exe) if exe and os.path.isabs(exe) else exe
    owner = system_desktop_owner(os.path.basename(fn)) if in_home(fn) else None
    if not owner and real and os.path.isabs(real) and not in_home(real):
        owner = dpkg_owner(real)
    if owner and owner in deb:
        info = deb[owner]
        item = Pkg(name, owner, 'apt', info['version'], info['size'], desc or info['summary'], icon,
                   level=deb_level(owner))
        # копия ярлыка и симлинк-запускалка в $HOME после удаления пакета станут мусором
        item.extra_files = [p for p in (fn, exe) if p and in_home(p) and (p == fn or os.path.islink(p))]
        return item

    if exe and in_home(exe) and in_home(real) and os.path.exists(exe):
        item = Pkg(name, os.path.basename(fn), 'local', summary=desc or exe, icon=icon)
        item.local = dict(kind='home', exe=exe, desktop=fn, icon_name=a.get_string('Icon'),
                          names={name, os.path.basename(fn)[:-len('.desktop')], os.path.basename(exe),
                                 a.get_string('Icon') or '', a.get_string('StartupWMClass') or ''})
        return item
    return Pkg(name, os.path.basename(fn), 'local', summary=desc or fn, icon=icon, removable=False,
               level='shortcut')


def path_size(path):
    if os.path.islink(path) or os.path.isfile(path):
        return os.lstat(path).st_size
    out = run(['du', '-sb', path]).split()
    return int(out[0]) if out and out[0].isdigit() else -1


def icon_files(icon_name):
    if not icon_name:
        return []
    if os.path.isabs(icon_name):
        return [icon_name] if in_home(icon_name) and os.path.exists(icon_name) else []
    res = []
    for base in (os.path.join(HOME, '.local/share/icons'), os.path.join(HOME, '.icons'),
                 os.path.join(HOME, '.local/share/pixmaps')):
        res += glob.glob(os.path.join(glob.escape(base), '**', glob.escape(icon_name) + '.*'), recursive=True)
    return res


def references(path, needles):
    try:
        with open(path, errors='ignore') as f:
            text = f.read(200_000)
    except OSError:
        return False
    return any(n and re.search(re.escape(n) + r'(?=$|[/\s"\';:])', text, re.M) for n in needles)


def plan_local(item):
    """Список того, что будет удалено: [{'kind','path','label','group','checked'}]. Вызывается в потоке."""
    L = item.local
    entries = []

    def add(path, label, group='program', checked=True, kind='path', note=''):
        if kind == 'path':
            if not path or not os.path.lexists(path) or not safe_to_delete(path):
                return
            if any(e['kind'] == 'path' and (path == e['path'] or path.startswith(e['path'] + '/')) for e in entries):
                return
        entries.append(dict(kind=kind, path=path, label=label, group=group, checked=checked, note=note))

    if L['kind'] == 'lutris':
        ldir = L['lutris_dir']
        try:
            con = lutris_connect(ldir)
            row = con.execute('select name, slug, directory, configpath from games where id=?',
                              (L['game_id'],)).fetchone()
            others = con.execute("select name, directory from games where id != ? and directory != ''",
                                 (L['game_id'],)).fetchall() if row else []
            con.close()
        except sqlite3.Error:
            row, others = None, []
        if row:
            _name, slug, directory, configpath = row
            if directory and safe_to_delete(directory):
                d = os.path.abspath(directory)
                # другие игры в той же папке (общий Wine-префикс, папка с ROM-ами) — не удалять по умолчанию
                shared = [n for n, od in others
                          if od and (os.path.abspath(od) == d or os.path.abspath(od).startswith(d + '/'))]
                add(directory, 'Файлы игры и Wine-префикс', checked=not shared, note=', '.join(shared[:3]))
            if configpath:
                add(os.path.join(ldir, 'games', configpath + '.yml'), 'Настройки игры в Lutris')
            for sub in ('banners', 'coverart'):
                for f in glob.glob(os.path.join(ldir, sub, glob.escape(slug) + '.*')):
                    add(f, 'Обложка')
            entries.append(dict(kind='lutris-db', path=str(L['game_id']), label='Запись в библиотеке Lutris',
                                group='program', checked=True, note='', lutris_dir=ldir))
        add(L['desktop'], 'Ярлык в меню')
        for f in icon_files(L['icon_name']):
            add(f, 'Значок')
        return merge_icons(entries)

    exe = L['exe']
    keys = app_keys(L['names'])
    roots = set()
    for p in (exe, os.path.realpath(exe)):
        r = install_root(p, keys)
        if r:
            roots.add(r)
    # Скрипт-запускалка: ищем исполняемые файлы в $HOME, на которые он ссылается
    try:
        if os.path.getsize(exe) < 64_000:
            with open(exe, errors='ignore') as f:
                text = f.read()
            for ref in re.findall(r'(?:\$HOME|~|' + re.escape(HOME) + r')(/[^\s"\'`;|&<>]+)', text):
                ref = HOME + ref
                if os.path.isfile(ref) and os.access(ref, os.X_OK):
                    rr = install_root(ref, keys)
                    if rr:
                        roots.add(rr)
    except OSError:
        pass
    for rr in sorted(roots):
        add(rr, 'Папка программы')
    add(exe, 'Исполняемый файл')
    add(L['desktop'], 'Ярлык в меню')
    for f in icon_files(L['icon_name']):
        add(f, 'Значок')

    needles = [exe, *roots]
    for unit in glob.glob(os.path.join(HOME, '.config/systemd/user/*.service')):
        if os.path.isfile(unit) and not os.path.islink(unit) and references(unit, needles):
            entries.append(dict(kind='unit', path=unit, label='Фоновая служба (будет остановлена)',
                                group='program', checked=True, note=''))
    for f in glob.glob(os.path.join(HOME, '.config/autostart/*.desktop')):
        if references(f, needles):
            add(f, 'Автозапуск')

    names = {n.lower() for n in L['names'] if n and len(n) >= 3}
    for base in ('.config', '.local/share', '.cache', '.local/state'):
        d = os.path.join(HOME, base)
        for entry in (os.listdir(d) if os.path.isdir(d) else []):
            if entry.lower() in names:
                add(os.path.join(d, entry), 'Данные и настройки', group='data', checked=False)
    for entry in os.listdir(HOME):
        if entry.startswith('.') and entry[1:].lower() in names:
            add(os.path.join(HOME, entry), 'Данные и настройки', group='data', checked=False)
    return merge_icons(entries)


def lutris_connect(ldir, write=False):
    """База игр Lutris. Только чтение, если не нужна запись; несуществующий файл не создаётся."""
    path = os.path.join(ldir, 'pga.db')
    if not os.path.isfile(path):
        raise sqlite3.OperationalError(f'{path} not found')
    if write:
        return sqlite3.connect(path)
    return sqlite3.connect(Path(path).as_uri() + '?mode=ro', uri=True)


def merge_icons(entries):
    """Объединяет значки разных размеров в один пункт."""
    icons = [e for e in entries if e['label'] == 'Значок']
    if len(icons) > 1:
        first = icons[0]
        first['more'] = [e['path'] for e in icons[1:]]
        first['count'] = len(icons)
        entries = [e for e in entries if e not in icons[1:]]
    return entries


def entry_paths(e):
    return [e['path'], *e.get('more', [])]


def entry_size(e):
    if e['kind'] != 'path':
        return -1
    return sum(max(path_size(p), 0) for p in entry_paths(e))


def process_alive(pid):
    try:
        with open(f'/proc/{pid}/stat') as f:
            return f.read().rsplit(')', 1)[1].split()[0] != 'Z'
    except (OSError, IndexError):
        return False


def kill_processes(roots, log):
    """Завершает процессы, запущенные из удаляемых путей, и ждёт их выхода (SIGTERM, затем SIGKILL)."""
    if not roots:
        return
    me = os.getpid()
    killed = []
    for pid in filter(str.isdigit, os.listdir('/proc')):
        if int(pid) == me:
            continue
        try:
            exe = os.readlink(f'/proc/{pid}/exe')
            with open(f'/proc/{pid}/cmdline', 'rb') as f:
                args = f.read().split(b'\0')[:3]
        except OSError:
            continue
        paths = [exe] + [a.decode(errors='ignore') for a in args]
        if any(p == r or p.startswith(r + '/') for p in paths for r in roots):
            try:
                os.kill(int(pid), signal.SIGTERM)
                killed.append(int(pid))
                log(tr('Завершён процесс {pid}: {name}\n', pid=pid, name=paths[1] or exe))
            except OSError:
                pass
    deadline = time.monotonic() + 5
    while killed and time.monotonic() < deadline:
        time.sleep(0.2)
        killed = [p for p in killed if process_alive(p)]
    for pid in killed:
        try:
            os.kill(pid, signal.SIGKILL)
            log(tr('Принудительно завершён процесс {pid}\n', pid=pid))
        except OSError:
            pass
    if killed:
        time.sleep(0.5)


def remove_local(entries, log):
    """Выполняет удаление по плану. Возвращает код (0 — успех)."""
    errors = 0
    for e in entries:
        if e['kind'] == 'unit':
            unit = os.path.basename(e['path'])
            log(tr('Останавливаю службу {unit}\n', unit=unit))
            subprocess.run(['systemctl', '--user', 'disable', '--now', unit],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    kill_processes([e['path'] for e in entries if e['kind'] == 'path' and os.path.isdir(e['path'])]
                   + [e['path'] for e in entries if e['label'] == 'Исполняемый файл'], log)
    for e in entries:
        if e['kind'] == 'lutris-db':
            try:
                con = lutris_connect(e['lutris_dir'], write=True)
                con.execute('delete from games where id=?', (int(e['path']),))
                con.commit()
                con.close()
                log(tr('Игра удалена из библиотеки Lutris\n'))
            except sqlite3.Error as ex:
                errors += 1
                log(tr('Ошибка базы Lutris: {err}\n', err=ex))
            continue
        for path in entry_paths(e):
            if not safe_to_delete(path):
                log(tr('Пропущено (небезопасный путь): {path}\n', path=path))
                continue
            try:
                if os.path.isdir(path) and not os.path.islink(path):
                    shutil.rmtree(path)
                elif os.path.lexists(path):
                    os.remove(path)
                log(tr('Удалено: {path}\n', path=path))
            except OSError as ex:
                errors += 1
                log(tr('Ошибка: {path}: {err}\n', path=path, err=ex))
    if any(e['kind'] == 'unit' for e in entries):
        subprocess.run(['systemctl', '--user', 'daemon-reload'])
    subprocess.run(['update-desktop-database', os.path.join(HOME, '.local/share/applications')],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 1 if errors else 0


def collect():
    """Собирает (приложения, все пакеты). Выполняется в фоновом потоке."""
    levels = classify_debs()

    def deb_level(pkg):
        return levels.get(pkg.split(':')[0], 'user')

    deb = {}
    out = run(['dpkg-query', '-W', '-f=${binary:Package}\t${Version}\t${Installed-Size}\t'
               '${db:Status-Abbrev}\t${binary:Summary}\n'])
    for line in out.splitlines():
        p = line.split('\t')
        if len(p) < 5 or not p[3].startswith('ii'):
            continue
        deb[p[0]] = dict(version=p[1], size=int(p[2]) * 1024 if p[2].isdigit() else -1, summary=p[4])
    manual = {m.split(':')[0] for m in run(['apt-mark', 'showmanual']).split()}

    snaps = {}
    for line in run(['snap', 'list']).splitlines()[1:]:
        p = line.split()
        if len(p) < 4:
            continue
        name, ver, rev = p[0], p[1], p[2]
        notes = p[5] if len(p) >= 6 else ''
        f = f'/var/lib/snapd/snaps/{name}_{rev}.snap'
        snaps[name] = dict(version=ver, size=os.path.getsize(f) if os.path.exists(f) else -1,
                           system=any(k in notes for k in ('base', 'core', 'snapd', 'kernel', 'gadget')))

    flats = {}
    for kind in ('--app', '--runtime'):
        out = run(['flatpak', 'list', kind, '--columns=application,name,version,size,installation'])
        for line in out.splitlines():
            p = line.split('\t')
            if len(p) < 5:
                continue
            flats.setdefault(p[0], dict(name=p[1], version=p[2], size=parse_size(p[3]),
                                        installation=p[4], runtime=kind == '--runtime'))

    # Приложения из меню (.desktop) и их пакеты
    infos = [a for a in Gio.AppInfo.get_all()
             if isinstance(a, DesktopAppInfo) and a.should_show() and a.get_filename()]
    deb_paths = [os.path.realpath(a.get_filename()) for a in infos]
    path_to_deb = {}
    if deb_paths:
        for line in run(['dpkg-query', '-S', *deb_paths]).splitlines():
            if line.startswith('diversion') or ': ' not in line:
                continue
            pkgs, path = line.rsplit(': ', 1)
            path_to_deb[path] = pkgs.split(',')[0].strip()

    apps, seen, icons = [], set(), {}
    for a in infos:
        fn = a.get_filename()
        name = a.get_display_name() or a.get_name()
        desc = a.get_description() or ''
        icon = a.get_icon()
        snap = a.get_string('X-SnapInstanceName')
        flat = a.get_string('X-Flatpak')
        if snap or '/snapd/desktop/' in fn:
            pkg = snap or os.path.basename(fn).split('_')[0]
            info = snaps.get(pkg, {})
            item = Pkg(name, pkg, 'snap', info.get('version', ''), info.get('size', -1), desc, icon,
                       level=snap_level(pkg, info.get('system', False)))
        elif flat or '/flatpak/exports/' in fn:
            pkg = flat or os.path.basename(fn)[:-len('.desktop')]
            info = flats.get(pkg, {})
            item = Pkg(name, pkg, 'flatpak', info.get('version', ''), info.get('size', -1), desc, icon,
                       installation=info.get('installation', 'system'),
                       level='system' if info.get('runtime') else 'user')
        elif os.path.realpath(fn) in path_to_deb:
            pkg = path_to_deb[os.path.realpath(fn)]
            info = deb.get(pkg, {})
            item = Pkg(name, pkg, 'apt', info.get('version', ''), info.get('size', -1),
                       desc or info.get('summary', ''), icon, level=deb_level(pkg))
        else:
            item = classify_local(a, fn, name, desc, icon, deb, deb_level)
        key = (item.source, item.pkg) if item.source in ('snap', 'flatpak') else fn
        if key in seen:
            continue
        seen.add(key)
        icons.setdefault((item.source, item.pkg), icon)
        apps.append(item)

    pkgs = []
    for name, i in deb.items():
        pkgs.append(Pkg(name, name, 'apt', i['version'], i['size'], i['summary'],
                        icons.get(('apt', name)), manual=name.split(':')[0] in manual, level=deb_level(name)))
    for name, i in snaps.items():
        pkgs.append(Pkg(name, name, 'snap', i['version'], i['size'], '',
                        icons.get(('snap', name)), manual=not i['system'], level=snap_level(name, i['system'])))
    for fid, i in flats.items():
        pkgs.append(Pkg(i['name'] or fid, fid, 'flatpak', i['version'], i['size'],
                        tr('Среда выполнения') if i['runtime'] else '', icons.get(('flatpak', fid)),
                        manual=not i['runtime'], installation=i['installation'],
                        level='system' if i['runtime'] else 'user'))
    return apps, pkgs


def make_spinner(size):
    if hasattr(Adw, 'Spinner'):  # libadwaita >= 1.6
        return Adw.Spinner(width_request=size, height_request=size)
    return Gtk.Spinner(spinning=True, width_request=size, height_request=size)


def ordering(x, y):
    return Gtk.Ordering.SMALLER if x < y else Gtk.Ordering.LARGER if x > y else Gtk.Ordering.EQUAL


class Window(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=tr('Установленные программы'),
                         default_width=1100, default_height=720)
        self.apps_store = Gio.ListStore(item_type=Pkg)
        self.pkgs_store = Gio.ListStore(item_type=Pkg)
        self.mode = 'apps'
        self.levels = {}
        self.alive = True   # окно могут закрыть (смена языка), пока работают фоновые потоки
        self.connect('destroy', lambda *_: setattr(self, 'alive', False))
        self.allow = Gio.SimpleAction.new_stateful('allow-protected', None, GLib.Variant('b', False))
        self.allow.connect('change-state', self.on_allow)
        self.add_action(self.allow)

        # --- Заголовок
        header = Adw.HeaderBar()
        # Переключатель режимов из связанных кнопок (работает на любой libadwaita)
        switcher = Gtk.Box(css_classes=['linked'])
        self.mode_buttons = {}
        for name, label in (('apps', tr('Приложения')), ('pkgs', tr('Все пакеты'))):
            b = Gtk.ToggleButton(label=label, active=name == 'apps')
            if self.mode_buttons:
                b.set_group(next(iter(self.mode_buttons.values())))
            b.connect('toggled', lambda btn, n=name: btn.get_active() and self.on_mode(n))
            self.mode_buttons[name] = b
            switcher.append(b)
        header.set_title_widget(switcher)
        refresh = Gtk.Button(icon_name='view-refresh-symbolic', tooltip_text=tr('Обновить список'))
        refresh.connect('clicked', lambda *_: self.reload())
        header.pack_start(refresh)
        menu = Gio.Menu()
        menu.append(tr('Разрешить удаление защищённых (опасно)'), 'win.allow-protected')
        lang_menu = Gio.Menu()
        lang_menu.append(tr('Как в системе'), "app.language('auto')")
        lang_menu.append('English', "app.language('en')")
        lang_menu.append('Русский', "app.language('ru')")
        menu.append_submenu(tr('Язык') + (' / Language' if LANG == 'ru' else ' / Язык'), lang_menu)
        header.pack_end(Gtk.MenuButton(icon_name='open-menu-symbolic', menu_model=menu))

        # --- Панель фильтров
        self.search = Gtk.SearchEntry(placeholder_text=tr('Поиск по названию или пакету…'), hexpand=True)
        self.search.connect('search-changed', lambda *_: self.refilter())
        self.source = Gtk.DropDown.new_from_strings([tr('Все источники'), 'APT', 'Snap', 'Flatpak'])
        self.source.connect('notify::selected', lambda *_: self.refilter())
        self.level = Gtk.DropDown.new_from_strings([tr(x) for x in ('Любой тип', 'Обычные', 'Системные', 'Защищённые')])
        self.level.connect('notify::selected', lambda *_: self.refilter())
        self.manual_only = Gtk.CheckButton(label=tr('Только установленные вручную'), active=True, visible=False)
        self.manual_only.connect('toggled', lambda *_: self.refilter())
        filters = Gtk.Box(spacing=8, margin_start=12, margin_end=12, margin_top=8, margin_bottom=8)
        for w in (self.search, self.source, self.level, self.manual_only):
            filters.append(w)

        # --- Таблица
        self.cv = Gtk.ColumnView(show_row_separators=True, reorderable=False)
        self.cv.add_css_class('data-table')
        self.filter = Gtk.CustomFilter.new(self.match)
        self.filter_model = Gtk.FilterListModel(model=self.apps_store, filter=self.filter)
        sort_model = Gtk.SortListModel(model=self.filter_model, sorter=self.cv.get_sorter())
        self.sel = Gtk.SingleSelection(model=sort_model, autoselect=False, can_unselect=True)
        self.sel.connect('notify::selected-item', lambda *_: self.update_buttons())
        self.cv.set_model(self.sel)
        self.cv.connect('activate', lambda *_: self.on_remove())
        self.filter_model.connect('items-changed', lambda *_: self.update_status())

        name_col = self.add_name_column()
        self.add_level_column()
        self.add_text_column(tr('Пакет'), lambda i: i.pkg, lambda i: i.pkg.lower(), 220)
        self.add_text_column(tr('Источник'), lambda i: tr(SOURCE_LABELS[i.source]), lambda i: i.source, 90)
        self.add_text_column(tr('Версия'), lambda i: i.version, lambda i: i.version, 150)
        self.add_text_column(tr('Размер'), lambda i: human_size(i.size), lambda i: i.size, 90, xalign=1)
        self.cv.sort_by_column(name_col, Gtk.SortType.ASCENDING)

        scroll = Gtk.ScrolledWindow(child=self.cv, vexpand=True)
        loading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                          valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER)
        loading.append(make_spinner(48))
        loading.append(Gtk.Label(label=tr('Собираю список программ…')))
        self.stack = Gtk.Stack()
        self.stack.add_named(loading, 'loading')
        self.stack.add_named(scroll, 'list')
        self.stack.add_named(Adw.StatusPage(icon_name='system-search-symbolic', title=tr('Ничего не найдено'),
                                            description=tr('Измените запрос или фильтры')), 'empty')

        # --- Нижняя панель
        self.status = Gtk.Label(xalign=0, hexpand=True, ellipsize=3, css_classes=['dim-label'])
        self.remove_btn = Gtk.Button(label=tr('Удалить'), css_classes=['destructive-action'], sensitive=False)
        self.remove_btn.connect('clicked', lambda *_: self.on_remove())
        bottom = Gtk.Box(spacing=8, margin_start=12, margin_end=12, margin_top=8, margin_bottom=8)
        self.disk_box = Gtk.Box(spacing=12, margin_end=12)
        bottom.append(self.status)
        bottom.append(self.disk_box)
        bottom.append(self.remove_btn)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        body.append(filters)
        body.append(self.stack)
        self.toasts = Adw.ToastOverlay(child=body)
        view = Adw.ToolbarView(content=self.toasts)
        view.add_top_bar(header)
        view.add_bottom_bar(bottom)
        self.set_content(view)

        keys = Gtk.EventControllerKey()
        keys.connect('key-pressed', self.on_key)
        self.add_controller(keys)
        self.reload()

    # ---------- колонки
    def add_name_column(self):
        def setup(_f, li):
            box = Gtk.Box(spacing=10, margin_top=4, margin_bottom=4)
            img = Gtk.Image(pixel_size=32)
            texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
            title = Gtk.Label(xalign=0, ellipsize=3, css_classes=['heading'])
            sub = Gtk.Label(xalign=0, ellipsize=3, css_classes=['dim-label', 'caption'])
            texts.append(title)
            texts.append(sub)
            box.append(img)
            box.append(texts)
            li.set_child(box)

        def bind(_f, li):
            item, box = li.get_item(), li.get_child()
            img = box.get_first_child()
            title = img.get_next_sibling().get_first_child()
            sub = title.get_next_sibling()
            if item.icon:
                img.set_from_gicon(item.icon)
            else:
                img.set_from_icon_name('application-x-executable' if self.mode == 'apps'
                                       else 'package-x-generic')
            title.set_label(item.name)
            sub.set_label(item.summary)
            sub.set_visible(bool(item.summary))
            box.set_tooltip_text(item.summary or None)

        f = Gtk.SignalListItemFactory()
        f.connect('setup', setup)
        f.connect('bind', bind)
        col = Gtk.ColumnViewColumn(title=tr('Название'), factory=f, expand=True, resizable=True)
        col.set_sorter(Gtk.CustomSorter.new(lambda a, b, _: ordering(a.name.lower(), b.name.lower()), None))
        self.cv.append_column(col)
        return col

    def add_level_column(self):
        def setup(_f, li):
            box = Gtk.Box(spacing=6)
            box.append(Gtk.Image(icon_name='emblem-system-symbolic'))
            box.append(Gtk.Label(xalign=0, ellipsize=3))
            li.set_child(box)

        def bind(_f, li):
            item, box = li.get_item(), li.get_child()
            img, lbl = box.get_first_child(), box.get_last_child()
            img.set_from_icon_name(LEVEL_ICONS[item.level])
            lbl.set_label(tr(LEVEL_LABELS[item.level]))
            for c in ('error', 'warning', 'dim-label'):
                box.remove_css_class(c)
            box.add_css_class(LEVEL_CSS.get(item.level, 'dim-label'))
            box.set_tooltip_text(tr({
                'protected': 'Нужно для работы системы — удаление может её сломать',
                'system': 'Входит в стандартную установку Ubuntu — удалять можно, но осторожно',
                'user': 'Установлено вами — можно спокойно удалять',
                'shortcut': 'Ярлык программы, установленной не через пакетный менеджер',
            }[item.level]))

        f = Gtk.SignalListItemFactory()
        f.connect('setup', setup)
        f.connect('bind', bind)
        col = Gtk.ColumnViewColumn(title=tr('Тип'), factory=f, fixed_width=160, resizable=True)
        col.set_sorter(Gtk.CustomSorter.new(
            lambda a, b, _: ordering(LEVEL_ORDER[a.level], LEVEL_ORDER[b.level]), None))
        self.cv.append_column(col)

    def add_text_column(self, title, text, key, width, xalign=0):
        f = Gtk.SignalListItemFactory()
        f.connect('setup', lambda _f, li: li.set_child(Gtk.Label(xalign=xalign, ellipsize=3)))

        def bind(_f, li):
            item, lbl = li.get_item(), li.get_child()
            lbl.set_label(text(item))
            li.handler = item.connect('changed', lambda it: lbl.set_label(text(it)))

        def unbind(_f, li):
            li.get_item().disconnect(li.handler)

        f.connect('bind', bind)
        f.connect('unbind', unbind)
        col = Gtk.ColumnViewColumn(title=title, factory=f, fixed_width=width, resizable=True)
        col.set_sorter(Gtk.CustomSorter.new(lambda a, b, _: ordering(key(a), key(b)), None))
        self.cv.append_column(col)

    # ---------- данные
    def reload(self):
        self.stack.set_visible_child_name('loading')

        def work():
            apps, pkgs = collect()
            GLib.idle_add(self.loaded, apps, pkgs)
        threading.Thread(target=work, daemon=True).start()

    def compute_local_sizes(self, apps):
        def work():
            for item in apps:
                if item.local and item.removable:
                    try:
                        item.size = sum(entry_size(e) for e in plan_local(item) if e['group'] == 'program') or -1
                    except OSError:
                        continue
            GLib.idle_add(self.refresh_rows, apps)
        threading.Thread(target=work, daemon=True).start()

    def refresh_rows(self, apps):
        if not self.alive:
            return
        for item in apps:
            if item.local:
                item.emit('changed')
        self.update_status()

    def loaded(self, apps, pkgs):
        if not self.alive:
            return
        self.apps_store.splice(0, self.apps_store.get_n_items(), apps)
        self.pkgs_store.splice(0, self.pkgs_store.get_n_items(), pkgs)
        self.levels = {p.pkg.split(':')[0]: p.level for p in pkgs if p.source == 'apt'}
        self.compute_local_sizes(apps)
        self.update_disk()
        self.stack.set_visible_child_name('list')
        self.update_status()
        self.update_buttons()

    def match(self, item):
        src = [None, 'apt', 'snap', 'flatpak'][self.source.get_selected()]
        if src and item.source != src:
            return False
        lvl = [None, ('user', 'shortcut'), ('system',), ('protected',)][self.level.get_selected()]
        if lvl and item.level not in lvl:
            return False
        if self.mode == 'pkgs' and self.manual_only.get_active() and not item.manual:
            return False
        q = self.search.get_text().strip().lower()
        return not q or q in item.name.lower() or q in item.pkg.lower() or q in item.summary.lower()

    def refilter(self):
        self.filter.changed(Gtk.FilterChange.DIFFERENT)
        self.update_status()

    def on_mode(self, mode):
        self.mode = mode
        self.manual_only.set_visible(self.mode == 'pkgs')
        self.filter_model.set_model(self.apps_store if self.mode == 'apps' else self.pkgs_store)
        self.refilter()

    def update_disk(self):
        """Занятое и свободное место на дисках с системой и домашней папкой."""
        while (child := self.disk_box.get_first_child()):
            self.disk_box.remove(child)
        seen = set()
        for mount, title in (('/', tr('Диск')), (HOME, tr('Домашний диск'))):
            try:
                st = os.statvfs(mount)
                dev = os.stat(mount).st_dev
            except OSError:
                continue
            if dev in seen or not st.f_blocks:
                continue
            seen.add(dev)
            total = st.f_blocks * st.f_frsize
            used = (st.f_blocks - st.f_bfree) * st.f_frsize
            free = st.f_bavail * st.f_frsize
            frac = used / total
            name = tr('Диск') if len(seen) == 1 else title
            bar = Gtk.LevelBar(value=frac, width_request=120, valign=Gtk.Align.CENTER)
            # стандартные уровни GTK рассчитаны на «мало — плохо» (как батарея); для диска наоборот
            for offset in (Gtk.LEVEL_BAR_OFFSET_LOW, Gtk.LEVEL_BAR_OFFSET_HIGH, Gtk.LEVEL_BAR_OFFSET_FULL):
                bar.remove_offset_value(offset)
            bar.add_offset_value('disk-ok', 0.9)
            bar.add_offset_value('disk-full', 1.0)
            lbl = Gtk.Label(label=tr('{name}: занято {used} из {total}  •  свободно {free}', name=name,
                                     used=human_size(used), total=human_size(total), free=human_size(free)))
            if frac > 0.9:
                lbl.add_css_class('error')
            box = Gtk.Box(spacing=8, tooltip_text=tr('{mount}: занято {pct}', mount=mount, pct=f'{frac:.0%}'))
            box.append(lbl)
            box.append(bar)
            self.disk_box.append(box)

    def update_status(self):
        if self.stack.get_visible_child_name() != 'loading':
            self.stack.set_visible_child_name('list' if self.filter_model.get_n_items() else 'empty')
        n = self.filter_model.get_n_items()
        total = sum(max(self.filter_model.get_item(i).size, 0) for i in range(n))
        self.status.set_label(tr('Показано: {n}   •   Занимают: {size}', n=n, size=human_size(total)))

    def protected_locked(self):
        return not self.allow.get_state().get_boolean()

    def update_buttons(self):
        item = self.sel.get_selected_item()
        tip = None
        ok = bool(item and item.removable)
        if item and not item.removable:
            tip = tr('Программа установлена вне домашней папки и не через пакет — удалить отсюда нельзя')
        elif item and item.level == 'protected' and self.protected_locked():
            ok, tip = False, tr('Защищённый компонент: от него зависит работа системы. '
                                'Разблокировать можно в меню ☰ (опасно).')
        self.remove_btn.set_sensitive(ok)
        name = item.name if item else ''
        self.remove_btn.set_label(tr('Удалить «{name}»', name=name[:30]) if item else tr('Удалить'))
        self.remove_btn.set_tooltip_text(tip)

    def on_allow(self, action, value):
        action.set_state(value)
        self.update_buttons()
        if value.get_boolean():
            self.toasts.add_toast(Adw.Toast(title=tr('Удаление защищённых пакетов разрешено. Будьте осторожны!')))

    def on_key(self, _c, keyval, _code, _state):
        if keyval == 0xffff and self.remove_btn.get_sensitive():  # Delete
            self.on_remove()
            return True
        return False

    # ---------- удаление
    def on_remove(self):
        item = self.sel.get_selected_item()
        if not item or not self.remove_btn.get_sensitive():
            return
        if item.source == 'apt':
            self.confirm_apt(item)
        elif item.source in ('local', 'lutris'):
            self.confirm_local(item)
        elif item.source == 'snap':
            self.confirm(item, self.level_warning(item) + tr('Будет удалён snap-пакет «{pkg}».', pkg=item.pkg),
                         lambda _purge: ['pkexec', 'snap', 'remove', item.pkg])
        else:
            inst = {'user': '--user', 'system': '--system'}.get(item.installation,
                                                                 f'--installation={item.installation}')
            self.confirm(item, self.level_warning(item) + tr('Будет удалён flatpak «{pkg}».', pkg=item.pkg),
                         lambda purge: ['flatpak', 'uninstall', '-y', '--noninteractive', inst,
                                        *(['--delete-data'] if purge else []), item.pkg],
                         purge_label=tr('Удалить также данные приложения'))

    def confirm_apt(self, item):
        def work():
            out = run(['apt-get', '-s', 'remove', item.pkg])
            removed = re.findall(r'^Remv (\S+)', out, re.M)
            installed = re.findall(r'^Inst (\S+)', out, re.M)
            errors = [l for l in out.splitlines() if l.startswith('E:')]
            GLib.idle_add(self.show_apt_confirm, item, removed, installed, errors)
        threading.Thread(target=work, daemon=True).start()

    def show_apt_confirm(self, item, removed, installed, errors):
        if not self.alive:
            return
        if not removed:
            self.toasts.add_toast(Adw.Toast(title=tr('Не удалось подготовить удаление: {err}',
                                                     err=errors[0] if errors else tr('нечего удалять'))))
            return
        critical = [p for p in removed if self.levels.get(p.split(':')[0]) == 'protected']
        system = [p for p in removed if self.levels.get(p.split(':')[0]) == 'system']
        if critical and self.protected_locked():
            dlg = Adw.AlertDialog(
                heading=tr('Удаление заблокировано'),
                body=tr('Вместе с «{name}» будут удалены защищённые системные пакеты ({n}), без которых Ubuntu '
                        'может не загрузиться или потерять рабочий стол:\n\n{list}\n\nЕсли вы точно знаете, '
                        'что делаете, включите в меню ☰ «Разрешить удаление защищённых».',
                        name=item.name, n=len(critical),
                        list=', '.join(critical[:15]) + (' …' if len(critical) > 15 else '')))
            dlg.add_response('ok', tr('Понятно'))
            dlg.present(self)
            return
        body = tr('Будут удалены пакеты ({n}):', n=len(removed))
        if installed:
            body = tr('Также будут установлены или обновлены пакеты ({n}): {list}\n\n', n=len(installed),
                      list=', '.join(installed[:10]) + (' …' if len(installed) > 10 else '')) + body
        if critical:
            body = tr('⚠ ОПАСНО: будут удалены защищённые системные пакеты ({list}). Система может перестать '
                      'работать!\n\n', list=', '.join(critical[:5]) + (' …' if len(critical) > 5 else '')) + body
        elif system:
            body = tr('Внимание: будут удалены компоненты стандартной установки Ubuntu ({list}).\n\n',
                      list=', '.join(system[:5]) + (' …' if len(system) > 5 else '')) + body
        self.confirm(item, body,
                     lambda purge: ['pkexec', 'env', 'DEBIAN_FRONTEND=noninteractive', 'apt-get',
                                    'purge' if purge else 'remove', '-y', item.pkg],
                     details='\n'.join(removed),
                     purge_label=tr('Удалить также настройки (purge)'))

    def confirm_local(self, item):
        def work():
            entries = plan_local(item)
            for e in entries:
                e['size'] = entry_size(e)
            lutris_running = item.source == 'lutris' and bool(run(['pgrep', '-x', 'lutris']).strip())
            GLib.idle_add(self.show_local_confirm, item, entries, lutris_running)
        threading.Thread(target=work, daemon=True).start()

    def show_local_confirm(self, item, entries, lutris_running):
        if not self.alive:
            return
        if not entries:
            self.toasts.add_toast(Adw.Toast(title=tr('Не нашёл файлов программы для удаления')))
            return
        body = tr('Игра установлена через Lutris.' if item.source == 'lutris' else
                  'Программа установлена вручную, не через пакетный менеджер.')
        body += tr(' Будут удалены отмеченные пункты (без возможности восстановления):')
        if lutris_running:
            body = tr('⚠ Lutris сейчас запущен — закройте его перед удалением.\n\n') + body
        dlg = Adw.AlertDialog(heading=tr('Удалить «{name}»?', name=item.name), body=body)
        dlg.add_response('cancel', tr('Отмена'))
        dlg.add_response('remove', tr('Удалить'))
        dlg.set_response_appearance('remove', Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.set_default_response('cancel')
        dlg.set_close_response('cancel')

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        checks = []
        for group, title in (('program', tr('Программа')), ('data', tr('Данные и настройки (оставьте, если планируете переустановить)'))):
            group_entries = [e for e in entries if e['group'] == group]
            if not group_entries:
                continue
            box.append(Gtk.Label(label=title, xalign=0, css_classes=['heading'], margin_top=8, wrap=True))
            for e in group_entries:
                path = e['path'].replace(HOME, '~', 1) if e['kind'] != 'lutris-db' else ''
                if e.get('more'):
                    path = os.path.dirname(os.path.dirname(path)) + '/…'
                size = f'  ({human_size(e["size"])})' if e['size'] >= 0 else ''
                cb = Gtk.CheckButton(active=e['checked'])
                label = tr('Значки ({n} шт.)', n=e['count']) if e.get('count') else tr(e['label'])
                if e.get('note'):
                    label += ' — ' + tr('также используется: {names}', names=e['note'])
                lbl = Gtk.Label(xalign=0, wrap=True, wrap_mode=2, use_markup=True,
                                label=f'{GLib.markup_escape_text(label)}{size}\n'
                                      f'<span size="small" alpha="65%">{GLib.markup_escape_text(path)}</span>'
                                      if path else GLib.markup_escape_text(label))
                cb.set_child(lbl)
                box.append(cb)
                checks.append((cb, e))
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_bottom(8)
        scroll = Gtk.ScrolledWindow(child=box, max_content_height=300, propagate_natural_height=True,
                                    hscrollbar_policy=Gtk.PolicyType.NEVER)
        dlg.set_extra_child(Gtk.Frame(child=scroll))

        def on_resp(_d, resp):
            chosen = [e for cb, e in checks if cb.get_active()]
            if resp == 'remove' and chosen:
                self.execute(item, func=lambda log: remove_local(chosen, log))
        dlg.connect('response', on_resp)
        dlg.present(self)

    def level_warning(self, item):
        if item.level == 'protected':
            return tr('⚠ ОПАСНО: это защищённый системный компонент. Система может перестать работать!\n\n')
        if item.level == 'system':
            return tr('Внимание: это часть стандартной установки системы.\n\n')
        return ''

    def confirm(self, item, body, make_cmd, details=None, purge_label=None):
        dlg = Adw.AlertDialog(heading=tr('Удалить «{name}»?', name=item.name), body=body)
        dlg.add_response('cancel', tr('Отмена'))
        dlg.add_response('remove', tr('Удалить'))
        dlg.set_response_appearance('remove', Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.set_default_response('cancel')
        dlg.set_close_response('cancel')
        extra = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        if details:
            lbl = Gtk.Label(label=details, xalign=0, selectable=True, css_classes=['monospace'])
            extra.append(Gtk.ScrolledWindow(child=lbl, min_content_height=min(200, 20 * details.count('\n') + 24),
                                            max_content_height=200, propagate_natural_height=True))
        purge = Gtk.CheckButton(label=purge_label) if purge_label else None
        if purge:
            extra.append(purge)
        dlg.set_extra_child(extra)

        def on_resp(_d, resp):
            if resp == 'remove':
                self.execute(item, make_cmd(purge.get_active() if purge else False))
        dlg.connect('response', on_resp)
        dlg.present(self)

    def set_busy(self, busy):
        """Пока идёт удаление, язык не переключается (окно пересоздаётся и журнал потерялся бы)."""
        action = self.get_application().lookup_action('language')
        if action:
            action.set_enabled(not busy)

    def execute(self, item, cmd=None, func=None):
        self.set_busy(True)
        buf = Gtk.TextBuffer()
        tv = Gtk.TextView(buffer=buf, editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR,
                          left_margin=8, right_margin=8, top_margin=8, bottom_margin=8)
        spinner = make_spinner(16)
        header = Adw.HeaderBar(show_end_title_buttons=False)
        header.pack_start(spinner)
        close = Gtk.Button(label=tr('Закрыть'), sensitive=False)
        header.pack_end(close)
        tbv = Adw.ToolbarView(content=Gtk.ScrolledWindow(child=tv, vexpand=True))
        tbv.add_top_bar(header)
        dlg = Adw.Dialog(title=tr('Удаление «{name}»', name=item.name), content_width=650, content_height=420,
                         child=tbv, can_close=False)
        close.connect('clicked', lambda *_: dlg.force_close())
        dlg.present(self)

        def append(text):
            buf.insert(buf.get_end_iter(), text)
            tv.scroll_to_mark(buf.get_insert(), 0, False, 0, 0)

        def finished(code):
            self.set_busy(False)
            spinner.set_visible(False)
            close.set_sensitive(True)
            dlg.set_can_close(True)
            cancelled = code in (126, 127) and cmd and cmd[0] == 'pkexec'
            if code == 0:
                append(tr('\n✔ Готово.\n'))
                self.toasts.add_toast(Adw.Toast(title=tr('«{name}» удалено', name=item.name)))
            elif cancelled:
                append(tr('\nОтменено: пароль не введён.\n'))
            else:
                append(tr('\n✘ Ошибка (код {code}).\n', code=code))
            if not cancelled:  # даже при ошибке часть могла удалиться
                self.reload()

        def log(text):
            GLib.idle_add(append, text)

        def work():
            if func:
                try:
                    code = func(log)
                except Exception as e:  # noqa: BLE001
                    log(f'{e}\n')
                    code = -1
                GLib.idle_add(finished, code)
                return
            try:
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     stdin=subprocess.DEVNULL, text=True, bufsize=1)
                for line in p.stdout:
                    GLib.idle_add(append, line)
                code = p.wait()
            except Exception as e:  # noqa: BLE001
                GLib.idle_add(append, f'{e}\n')
                code = -1
            if code == 0 and item.extra_files:
                remove_local([dict(kind='path', path=f, label='Ярлык', note='') for f in item.extra_files], log)
            GLib.idle_add(finished, code)
        if cmd:
            append('$ ' + ' '.join(cmd) + '\n\n')
        threading.Thread(target=work, daemon=True).start()


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_startup(self):
        Adw.Application.do_startup(self)
        Gtk.Window.set_default_icon_name(APP_ID)
        error = 'var(--error-bg-color)' if Adw.get_minor_version() >= 6 else '@error_bg_color'
        css = Gtk.CssProvider()
        css.load_from_string(f'levelbar > trough > block.disk-full {{ background-color: {error}; }}')
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        choice = load_settings().get('language', 'auto')
        action = Gio.SimpleAction.new_stateful('language', GLib.VariantType.new('s'), GLib.Variant('s', choice))
        action.connect('change-state', self.on_language)
        self.add_action(action)

    def on_language(self, action, value):
        if value.equal(action.get_state()):
            return
        action.set_state(value)
        settings = load_settings()
        settings['language'] = value.get_string()
        try:
            save_settings(settings)
        except OSError:
            pass
        apply_language(value.get_string())
        old = self.props.active_window
        win = Window(self)
        win.present()
        if old:
            old.destroy()

    def do_activate(self):
        (self.props.active_window or Window(self)).present()


def main():
    if (Adw.get_major_version(), Adw.get_minor_version()) < (1, 5):
        print(f'libadwaita 1.5+ is required (Ubuntu 24.04+), found '
              f'{Adw.get_major_version()}.{Adw.get_minor_version()}', file=sys.stderr)
        return 1
    return App().run(sys.argv)


if __name__ == '__main__':
    sys.exit(main())
