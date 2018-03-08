#!/usr/bin/env python3
# coding: utf-8

from datetime import datetime
import optparse
import os
import subprocess
import sys
from . import version

cfn_dryrun = False


def print_command(*cmd):
    print("\033[92m", ' '.join(cmd), "\033[0m")


def print_error(msg):
    print("\033[91m", msg, "\033[0m", file=sys.stderr)


def cfn(action, *args):
    arg = ' '.join(args)
    print_command(f"aws cloudformation {action} {arg}")
    if not cfn_dryrun:
        subprocess.run(["aws", "cloudformation", action]+arg.split())


def _template_body(file):
    if os.path.exists(file):
        return f"--template-body file://{file}"
    else:
        print_error(f"template file {file} not found")
        sys.exit(1)


def _parameters(file):
    if os.path.exists(file):
        return f"--parameters file://{file}"
    else:
        return ''


def _stack_policy_body(file):
    if os.path.exists(file):
        return f"--stack-policy-body file://{file}"
    else:
        print_error(f"policy file {file} not found")
        sys.exit(1)


def _capabilities(capabilities):
    if capabilities == '':
        return ''
    else:
        return f"--capabilities {capabilities}"


def set_stack_policy(stack):
    cfn('set-stack-policy', '--stack-name', stack, _stack_policy_body)


def action_create(stack, files, opts):
    cfn('create-stack', '--stack-name', stack,
        _template_body(files['template']),
        _parameters(files['parameters']),
        _capabilities(files['capabilities']),
        '--disable-rollback'
        )
    cfn('wait', 'stack-create-complete', '--stack-name', stack)


def action_update(stack, files, opts):
    date = datetime.now().strftime('%Y%m%d%H%M%S')
    change_set_name = f"{stack}-change-set-{date}"

    cfn('create-change-set', '--stack-name', stack,
        _template_body(files['template']),
        _parameters(files['parameters']),
        _capabilities(files['capabilities']),
        '--change-set-name', change_set_name,
        )
    cfn('wait', 'change-set-create-complete', '--stack-name', stack,
        '--change-set-name', change_set_name)
    cfn('describe-change-set', '--stack-name', stack,
        '--change-set-name', change_set_name)

    if input('do update? [y|N]: ') != 'y':
        return

    set_stack_policy(stack)

    cfn('execute-change-set', '--stack-name',
        stack, '--change-set-name', change_set_name)
    cfn('wait', 'stack-update-complete', '--stack-name', stack)


def action_delete(stack, files, opts):
    print(f"""
Attempt to delete '{stack}' Stack.
This action CANNOT be undone.
Are you ABSOLUTELY sure?
    """.strip())
    print()
    confirm = input('Please type in the name of the stack to confirm: ')
    if confirm == stack:
        cfn('delete-stack', '--stack-name', stack)
        cfn('wait', 'stack-delete-complete', '--stack-name', stack)
    else:
        print_error('Aborted.')
        return


def action_validate(stack, files, opts):
    cfn('validate-template', _template_body(files['template']))


help_text = """%prog [OPTIONS] ACTION STACK

Actions:
    create      create stack
    update      update stack after show diffs with currently deployed stack
    delete      delete stack
    validate    validate template

Options:
    -n, --dry-run       only shows command-lines
    -s, --stack-name    specify stack name
    -c, --capabilities  specify capabilities
    -e, --environment   specify environment
    -p, --profile       specify AWS_PROFILE
"""


class UsageError(BaseException):
    pass


def main():
    parser = optparse.OptionParser(
        usage=help_text,
        version='%prog v'+version,
    )
    parser.add_option('-s', '--stack-name', dest='stack_name')
    parser.add_option('-c', '--capabilities', dest='capabilities')
    parser.add_option('-e', '--environment', dest='environment')
    parser.add_option('-p', '--profile', dest='profile')
    parser.add_option('--dry-run', dest='dryrun', action='store_true')

    opts, args = parser.parse_args()
    if len(args) != 2:
        parser.print_help()
        sys.exit(129)

    global cfn_dryrun
    cfn_dryrun = opts.dryrun

    if opts.profile is not None:
        os.environ['AWS_PROFILE'] = opts.profile

    cur_dir = os.getcwd()
    stacks_dir = os.path.join(cur_dir, 'stacks')

    action, stack = args[0], args[1]
    project = os.path.basename(os.path.abspath(os.path.join(stacks_dir, '..')))
    environment = opts.environment if opts.environment is not None else 'prod'
    stack_name = opts.stack_name if opts.stack_name is not None else f"{project}-{environment}-{stack}"

    files = {
        "template": f"{stacks_dir}/{stack}/template.yml",
        "parameter": f"{stacks_dir}/{stack}/parameters/{environment}.yml",
        "policy": f"{stacks_dir}/{stack}/policy.yml",
    }
    try:
        if action == 'create':
            action_create(stack_name, files, opts)
        elif action == 'update':
            action_update(stack_name, files, opts)
        elif action == 'delete':
            action_delete(stack_name, files, opts)
        elif action == 'validate':
            action_validate(stack_name, files, opts)
        else:
            raise UsageError()
    except UsageError:
        parser.print_help()
        sys.exit(129)


if __name__ == '__main__':
    main()
