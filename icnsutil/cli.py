#!/usr/bin/env python3
'''
Export existing icns files or compose new ones.
'''
import os  # path, makedirs
import sys  # path, stderr
from typing import Iterator, Optional, Callable
from argparse import ArgumentParser, ArgumentTypeError, RawTextHelpFormatter
from argparse import Namespace as ArgParams
if __name__ == '__main__':
    sys.path[0] = os.path.dirname(sys.path[0])
from icnsutil import __version__, IcnsFile, IcnsType, ArgbImage


def cli_extract(args: ArgParams) -> None:
    ''' Read and extract contents of icns file(s). '''
    multiple = len(args.file) > 1 or '-' in args.file
    for i, fname in enumerate(enum_with_stdin(args.file)):
        # PathExist ensures that all files and directories exist
        out = args.export_dir
        if out and multiple:
            out = os.path.join(out, str(i))
            os.makedirs(out, exist_ok=True)

        IcnsFile(fname).export(
            out, allowed_ext='png' if args.png_only else '*',
            recursive=args.recursive, convert_png=args.convert,
            key_suffix=args.keys)


def cli_compose(args: ArgParams) -> None:
    ''' Create new icns file from provided image files. '''
    dest = args.target
    if not os.path.splitext(dest)[1]:
        dest += '.icns'  # for the lazy people
    if not args.force and os.path.exists(dest):
        print(
            'File "{}" already exists. Force overwrite with -f.'.format(dest),
            file=sys.stderr)
        return
    img = IcnsFile()
    for x in enum_with_stdin(args.source):
        img.add_media(file=x)
    img.write(dest, toc=not args.no_toc)


def cli_update(args: ArgParams) -> None:
    ''' Update existing icns file by inserting or removing media entries. '''
    icns = IcnsFile(args.file)
    has_changes = False
    # remove media
    for x in args.rm or []:
        has_changes |= icns.remove_media(IcnsType.key_from_readable(x))
    # add media
    for key_val in args.set or []:
        def fail():
            raise ArgumentTypeError(
                'Expected arg format KEY=FILE - got "{}"'.format(key_val))
        if '=' not in key_val:
            fail()
        key, val = key_val.split('=', )
        if not val:
            fail()
        if not os.path.isfile(val):
            raise ArgumentTypeError('File does not exist "{}"'.format(val))

        icns.add_media(IcnsType.key_from_readable(key), file=val, force=True)
        has_changes = True
    # write file
    if has_changes or args.output:
        icns.write(args.output or args.file, toc=icns.has_toc())


def cli_print(args: ArgParams) -> None:
    ''' Print contents of icns file(s). '''
    for fname in enum_with_stdin(args.file):
        print('File:', fname)
        print(IcnsFile.description(fname, verbose=args.verbose, indent=2))


def cli_verify(args: ArgParams) -> None:
    ''' Test if icns file is valid. '''
    for fname in enum_with_stdin(args.file):
        is_valid = True  # type: Optional[bool]
        if not args.quiet:
            print('File:', fname)
            is_valid = None
        for issue in IcnsFile.verify(fname):
            if is_valid:
                print('File:', fname)
            is_valid = False
            print(' ', issue)
        if not args.quiet and is_valid is not False:
            print('OK')


def cli_convert(args: ArgParams) -> None:
    ''' Convert images between PNG, ARGB, or RGB + alpha mask. '''
    img = ArgbImage(file=args.source)
    if args.mask:
        img.load_mask(file=args.mask)

    dest = args.target
    if args.target in ['png', 'argb', 'rgb']:
        dest = args.source + '.' + args.target

    ext = os.path.splitext(dest)[1]
    if ext == '.png':
        img.write_png(dest)
    elif ext == '.argb':
        with open(dest, 'wb') as fp:
            fp.write(img.argb_data())
    elif ext == '.rgb':
        with open(dest, 'wb') as fp:
            if not args.raw and img.size == (128, 128):
                fp.write(b'\x00\x00\x00\x00')  # fix for it32
            fp.write(img.rgb_data())
        with open(dest + '.mask', 'wb') as fp:
            fp.write(img.mask_data())
    else:
        print('Could not determine target image-type for file "{}".'.format(
            dest), file=sys.stderr)


def enum_with_stdin(file_arg: list) -> Iterator[str]:
    for x in file_arg:
        if x == '-':
            for line in sys.stdin.readlines():
                yield line.strip()
        else:
            yield x


def main() -> None:
    class PathExist:
        def __init__(self, kind: Optional[str] = None, stdin: bool = False):
            self.kind = kind
            self.stdin = stdin

        def __call__(self, path: str) -> str:
            if self.stdin and path == '-':
                return '-'
            if not os.path.exists(path) or \
                    self.kind == 'f' and not os.path.isfile(path) or \
                    self.kind == 'd' and not os.path.isdir(path):
                raise ArgumentTypeError('Does not exist "{}"'.format(path))
            return path

    # Args Parser
    parser = ArgumentParser(description=__doc__,
                            formatter_class=RawTextHelpFormatter)
    parser.set_defaults(func=lambda _: parser.print_help(sys.stderr))
    parser.add_argument(
        '-v', '--version', action='version', version='icnsutil ' + __version__)
    sub_parser = parser.add_subparsers(metavar='command')

    # helper method
    def add_command(name: str, alias: str, fn: Callable[[ArgParams], None]):
        desc = fn.__doc__ or ''
        cmd = sub_parser.add_parser(name, aliases=[alias],
                                    formatter_class=RawTextHelpFormatter,
                                    help=desc, description=desc.strip())
        cmd.set_defaults(func=fn)
        return cmd

    # Extract
    cmd = add_command('extract', 'e', cli_extract)
    cmd.add_argument('-r', '--recursive', action='store_true',
                     help='extract nested icns files as well')
    cmd.add_argument('-o', '--export-dir', type=PathExist('d'),
                     metavar='DIR', help='set custom export directory')
    cmd.add_argument('-k', '--keys', action='store_true',
                     help='use icns key as filenam')
    cmd.add_argument('-c', '--convert', action='store_true',
                     help='convert ARGB and RGB images to PNG')
    cmd.add_argument('--png-only', action='store_true',
                     help='do not extract ARGB, binary, and meta files')
    cmd.add_argument('file', type=PathExist('f', stdin=True), nargs='+',
                     metavar='FILE', help='One or more .icns files')

    # Compose
    cmd = add_command('compose', 'c', cli_compose)
    cmd.add_argument('-f', '--force', action='store_true',
                     help='force overwrite output file')
    cmd.add_argument('--no-toc', action='store_true',
                     help='do not write table of contents to file')
    cmd.add_argument('target', type=str, metavar='destination',
                     help='Output file for newly created icns file.')
    cmd.add_argument('source', type=PathExist('f', stdin=True), nargs='+',
                     metavar='src',
                     help='One or more media files: png, argb, plist, icns.')
    cmd.epilog = '''
Notes:
- TOC is optional but only a few bytes long (8b per media entry).
- Icon dimensions are read directly from file.
- Filename suffix "@2x.png" or "@2x.jp2" sets the retina flag.
- Use one of these suffixes to automatically assign icns files:
   template, selected, dark
'''

    # Update
    cmd = add_command('update', 'u', cli_update)
    cmd.add_argument('file', type=PathExist('f', stdin=True),
                     metavar='FILE', help='The icns file to be updated.')
    cmd.add_argument('-o', '--output', type=str, metavar='OUT_FILE',
                     help='Choose another destination, dont overwrite input.')
    grp = cmd.add_argument_group('action')
    grp.add_argument('-rm', type=str, nargs='+', metavar='KEY',
                     help='Remove media keys from icns file')
    grp.add_argument('-set', type=str, nargs='+', metavar='KEY=FILE',
                     help='Append or replace media in icns file')
    cmd.epilog = 'KEY supports names like "dark", "selected", and "template"'

    # Print
    cmd = add_command('print', 'p', cli_print)
    cmd.add_argument('-v', '--verbose', action='store_true',
                     help='print all keys with offsets and sizes')
    cmd.add_argument('file', type=PathExist('f', stdin=True), nargs='+',
                     metavar='FILE', help='One or more .icns files.')

    # Verify
    cmd = add_command('test', 't', cli_verify)
    cmd.add_argument('-q', '--quiet', action='store_true',
                     help='do not print OK results')
    cmd.add_argument('file', type=PathExist('f', stdin=True), nargs='+',
                     metavar='FILE', help='One or more .icns files.')

    # Convert
    cmd = add_command('convert', 'img', cli_convert)
    cmd.add_argument('--raw', action='store_true',
                     help='no post-processing. Do not prepend it32 header.')
    cmd.add_argument('target', type=str, metavar='destination',
                     help='Image type determined by extension (png|argb|rgb)')
    cmd.add_argument('source', type=PathExist('f'), metavar='src',
                     help='Input image (png|argb|rgb|jp2)')
    cmd.add_argument('mask', type=PathExist('f'), nargs='?',
                     help='Alpha mask. If set, assume src is RGB image.')

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
