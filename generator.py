#! /usr/bin/env python3

import sys
import yaml
import argparse
import jinja2
import mistletoe
from mistletoe import Document
import os
import shutil
import subprocess
import logging

def set_logging(loglevel, logfile):
    # Setting the loglevel
    numeric_level = getattr(logging, args.loglevel.upper(), None)
    handlers = []
    handlers.append(logging.StreamHandler(sys.stdout))
    if args.logfile is not None:
        handlers.append(logging.FileHandler(args.logfile))

    logging.basicConfig(
            format='%(asctime)s - %(levelname)s - %(message)s',
            level=numeric_level,
            handlers=handlers
        )


def get_first_heading(markdown):
    lines = markdown.split("\n")
    for l in lines:
        if l.startswith('# '):
            return l.replace('# ', '').strip()


def get_config(projectdir):
    with open('{}/config.yml'.format(projectdir), 'r') as configfile:
        config = yaml.safe_load(configfile)

    return config


def parse_markdown_with_front_matter(file_path):
    # Read the file and parse with mistletoe
    with open(file_path, 'r', encoding='utf-8') as file:
        raw = file.read()

        document = Document.read(raw, front_matter=True)

    # Extract front matter and markdown content
    if document.front_matter is not None:
        front_matter_data = document.front_matter.get_data()
    else:
        front_matter_data = {}

    with mistletoe.HTMLRenderer() as renderer:
        parsed_markdown = renderer.render(document)

    return front_matter_data, parsed_markdown, raw


def main_generate(args):
    set_logging(args.loglevel, args.logfile)

    config = get_config(args.projectdir)

    # Additional variables
    var = {}
    if 'var' in config:
        for v in config['var']:
            var[v] = config['var'][v]

    # Emptying build folder
    builddir = '{}/build/'.format(args.projectdir)
    if os.path.exists(builddir):
        logging.debug('Removing the build folder.')
        shutil.rmtree(builddir)

    # Walking the content folder, copying and rendering
    for root, dirs, files in os.walk('{}/{}'.format(args.projectdir, 'content/')):
        dest = '{}{}'.format(builddir, root.replace('{}/content/'.format(args.projectdir), ''))
        os.mkdir(dest)
        for file in files:
            if not file.endswith('md'):
                # Copy the file
                shutil.copy('{}/{}'.format(root, file), '{}/{}'.format(dest, file))
            else:
                # Turn the file into html
                file_path = '{}/{}'.format(root, file).replace('//', '/')
                front_matter, content, raw = parse_markdown_with_front_matter(file_path)


                # Render the article with the template it wants - with limits.
                default_template = 'default.html'
                if 'template' not in front_matter:
                    logging.debug('template not set in source file')
                    template = default_template
                elif not os.path.exists('{}/templates/{}'.format(args.projectdir, front_matter['template'])):
                    logging.warning('Invalid template file "{}" for source "{}". Fallback to default template "{}".'.format(front_matter['template'], file_path, default_template))
                    template = default_template
                else:
                    logging.debug('Using template file from source file.')
                    template = front_matter['template']

                # Template environment
                env = jinja2.Environment(loader=jinja2.FileSystemLoader('{}/templates'.format(args.projectdir), encoding='utf8'))
                template = env.get_template(template)

                var['title'] = get_first_heading(raw)
                logging.debug('Setting title to {}'.format(var['title']))

                if 'title' in front_matter:
                    var['title'] = front_matter['title']
                    logging.debug('Overwriting title to {}'.format(var['title']))

                # Rendering Markdown so that variables used there get replaced
                contentenv = jinja2.Environment(loader=jinja2.BaseLoader).from_string(content)
                try:
                    content = contentenv.render(var=var)
                except:
                    logging.critical('Markdown Rendering failed.')
                    sys.exit(1)

                # Rendering the whole page
                try:
                    logging.debug('Actually rendering file {}'.format(file_path))
                    html = template.render(content=content, var=var)
                except:
                    logging.critical('Rendering of source "{}" to html failed.'.format(file_path))
                    sys.exit(1)

                # Safe the page to the build folder.
                with open('{}/{}.html'.format(dest, os.path.splitext(file)[0]), 'w') as f:
                    f.write(html)


def main_sync(args):
    set_logging(args.loglevel, args.logfile)

    builddir = '{}/build/'.format(args.projectdir)

    config = get_config(args.projectdir)

    dest = config['sync'][args.environment]['dest']

    logging.info('Starting rsync.')
    try:
        subprocess.check_call('rsync -az --delete {} {}'.format(builddir, dest), shell=True)
    except:
        logging.critical('Rsync failed.')
        sys.exit(1)

    logging.info('rsync done.')


parser = argparse.ArgumentParser(description="Ben's Homepage Generator.")
parser.add_argument('--loglevel', help='Setting the loglevel.', choices=['critical', 'error', 'warning', 'info', 'debug'], default='INFO')
parser.add_argument('--logfile', help='Output logs to given logfile.')
parser.add_argument('projectdir', help="Path to the project folder. There needs to be 'templates' and a 'content' folder.")

subparsers = parser.add_subparsers()
sub_gen = subparsers.add_parser('generate', aliases=['gen'], description='Generate the site.', help='Generate the site.')
sub_gen.set_defaults(func=main_generate)

sub_sync = subparsers.add_parser('sync', description='Sync build folder to environment.', help='Sync build folder to environment.')
sub_sync.add_argument('environment', help='The environment within config.yml to sync to.')
sub_sync.set_defaults(func=main_sync)

args = parser.parse_args()
if 'func' in args:
    args.func(args)
else:
    parser.parse_args(['--help'])
