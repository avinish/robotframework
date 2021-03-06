import unittest
import os

from robot.utils.argumentparser import ArgumentParser
from robot.utils.asserts import (assert_equals, assert_raises,
                                 assert_raises_with_msg, assert_true)
from robot.errors import Information, DataError, FrameworkError
from robot.version import get_full_version


USAGE = """Example Tool -- Stuff before hyphens is considered name

Usage:  robot.py [options] datafile

Version: <VERSION>

Options:
  -d --reportdir dir        Explanation
  -r --reportfile file      This explanation continues ............... 78
       ........... to multiple lines.
       Next line is totally empty.

  -E --escape what:with *      Line below has nothing after '*'. Next line has
          nothing after value and next nothing after option name
  -v --variable name:value *
  -N --name name
  -t -T --toggle   Something
  -h -? --help
  --version  Explanation

  -z   No long option so not an option line.
  --z  No long option here either
  this line doesn't start with a '-' so not an --optionline
  -\\-option     escaped 1
  -o -\\-option  escaped 2
          --ignored  options cannot be this far
          --ignored

* denotes options that can be set multiple times
"""

USAGE2 = """Just Name Here
usage:  robot.py [options] arg1 arg2

options:
  -v --variable name=value
  -x --var-able name=v1,v2   Explanation
  -3 --42
  --help
"""


class TestArgumentParserInit(unittest.TestCase):

    def setUp(self):
        self.ap = ArgumentParser(USAGE)

    def test_short_options(self):
        assert_equals(self.ap._short_opts, 'd:r:E:v:N:tTh?')

    def test_long_options(self):
        expected = ['reportdir=', 'reportfile=', 'escape=', 'variable=',
                    'name=', 'toggle', 'help', 'version']
        assert_equals(self.ap._long_opts, expected)

    def test_multi_options(self):
        assert_equals(self.ap._multi_opts, ['escape', 'variable'])

    def test_toggle_options(self):
        assert_equals(self.ap._toggle_opts, ['toggle', 'help', 'version'])

    def test_options_must_be_indented_by_1_to_four_spaces(self):
        ap = ArgumentParser('''Name
1234567890
--notin  this option is not indented at all and thus ignored
 --opt1
    --opt2        This option is 4 spaces from left -> included
    -o --opt3 argument  It doesn't matter how far the option gets.
     --notopt     This option is 5 spaces from left -> not included
     -i --ignored
                     --not-in-either
    --included  back in four space indentation''')
        assert_equals(ap._long_opts, ['opt1', 'opt2', 'opt3=', 'included'])

    def test_case_insensitive_long_options(self):
        ap = ArgumentParser(' -f --foo\n -B --BAR\n')
        assert_equals(ap._short_opts, 'fB')
        assert_equals(ap._long_opts, ['foo','bar'])

    def test_same_option_multiple_times(self):
        for my_usage in [' --foo\n --foo\n',
                         ' --foo\n -f --Foo\n',
                         ' -x --foo xxx\n -y --Foo yyy\n',
                         ' -f --foo\n -f --bar\n']:
            assert_raises(FrameworkError, ArgumentParser, my_usage)
        ap = ArgumentParser(' -f --foo\n -F --bar\n')
        assert_equals(ap._short_opts, 'fF')
        assert_equals(ap._long_opts, ['foo','bar'])


class TestArgumentParserParseArgs(unittest.TestCase):

    def setUp(self):
        self.ap = ArgumentParser(USAGE)

    def test_missing_argument_file_throws_data_error(self):
        inargs = '--argumentfile missing_argument_file_that_really_is_not_there.txt'.split()
        self.assertRaises(DataError, self.ap.parse_args, inargs)

    def test_single_options(self):
        inargs = '-d reports --reportfile report.html -T arg'.split()
        opts, args = self.ap.parse_args(inargs)
        assert_equals(opts, {'reportdir':'reports', 'reportfile':'report.html',
                             'variable':[], 'name':None, 'toggle': True})

    def test_multi_options(self):
        inargs = '-v a:1 -v b:2 --name my_name --variable c:3 arg'.split()
        opts, args = self.ap.parse_args(inargs)
        assert_equals(opts, {'variable':['a:1','b:2','c:3'], 'name':'my_name',
                             'reportdir':None, 'reportfile':None,
                             'toggle': False})
        assert_equals(args, ['arg'])

    def test_toggle_options(self):
        for inargs, exp in [('arg', False),
                            ('--toggle arg', True),
                            ('--toggle --name whatever -t arg', False),
                            ('-t -T --toggle arg', True)]:
            opts, args = self.ap.parse_args(inargs.split())
            assert_equals(opts['toggle'], exp)
            assert_equals(args, ['arg'])

    def test_single_option_multiple_times(self):
        for inargs in ['--name Foo -N Bar arg',
                       '-N Zap --name Foo --name Bar arg',
                       '-N 1 -N 2 -N 3 -t --variable foo -N 4 --name Bar arg']:
            opts, args = self.ap.parse_args(inargs.split())
            assert_equals(opts['name'], 'Bar')
            assert_equals(args, ['arg'])

    def test_case_insensitive_long_options(self):
        opts, args = self.ap.parse_args('--VarIable X:y --TOGGLE arg'.split())
        assert_equals(opts['variable'], ['X:y'])
        assert_equals(opts['toggle'], True)
        assert_equals(args, ['arg'])

    def test_case_insensitive_long_options_with_equal_sign(self):
        opts, args = self.ap.parse_args('--VariAble=X:y --VARIABLE=ZzZ'.split())
        assert_equals(opts['variable'], ['X:y', 'ZzZ'])
        assert_equals(args, [])

    def test_unescape_options(self):
        cli = '--escape quot:Q -E space:SP -E lt:LT -E gt:GT ' \
                + '-N QQQLTmySPfineSPnameGTQQQ sourceSPwithSPspaces'
        opts, args = self.ap.parse_args(cli.split())
        assert_equals(opts['name'], '"""<my fine name>"""')
        assert_equals(args, ['source with spaces'])
        assert_true('escape' not in opts)

    def test_split_pythonpath(self):
        ap = ArgumentParser('ignored')
        data = [(['path'], ['path']),
                (['path1','path2'], ['path1','path2']),
                (['path1:path2'], ['path1','path2']),
                (['p1:p2:p3','p4','.'], ['p1','p2','p3','p4','.'])]
        if os.sep == '\\':
            data += [(['c:\\path'], ['c:\\path']),
                     (['c:\\path','d:\\path'], ['c:\\path','d:\\path']),
                     (['c:\\path:d:\\path'], ['c:\\path','d:\\path']),
                     (['c:/path:x:yy:d:\\path','c','.','x:/xxx'],
                      ['c:\\path', 'x', 'yy', 'd:\\path', 'c', '.', 'x:\\xxx'])]
        for inp, exp in data:
            assert_equals(ap._split_pythonpath(inp), exp)

    def test_get_pythonpath(self):
        ap = ArgumentParser('ignored')
        p1 = os.path.abspath('.')
        p2 = os.path.abspath('..')
        assert_equals(ap._get_pythonpath(p1), [p1])
        assert_equals(ap._get_pythonpath([p1,p2]), [p1,p2])
        assert_equals(ap._get_pythonpath([p1 + ':' + p2]), [p1,p2])
        assert_true(p1 in ap._get_pythonpath(os.path.join(p2,'*')))

    def test_arguments_are_globbed(self):
        _, args = self.ap.parse_args([__file__.replace('test_', '?????')])
        assert_equals(args, [__file__])
        # Needed to ensure that the globbed directory contains files
        globexpr = os.path.join(os.path.dirname(__file__), '*')
        _, args = self.ap.parse_args([globexpr])
        assert_true(len(args) > 1)

    def test_arguments_with_glob_patterns_arent_removed_if_they_dont_match(self):
        _, args = self.ap.parse_args(['*.non.existing', 'non.ex.??'])
        assert_equals(args, ['*.non.existing', 'non.ex.??'])

    def test_special_options_are_removed(self):
        ap = ArgumentParser('''Usage:
 -h --help
 -v --version
 --pythonpath path
 --escape x:y *
 --argumentfile path
 --option
''')
        opts, args = ap.parse_args(['--option'])
        assert_equals(opts, {'option': True})

    def test_special_options_can_be_turned_to_normal_optios(self):
        ap = ArgumentParser('''Usage:
 -h --help
 -v --version
 --pythonpath path
 --escape x:y
 --argumentfile path
''', auto_help=False, auto_version=False, auto_escape=False,
     auto_pythonpath=False, auto_argumentfile=False)
        opts, args = ap.parse_args(['--help', '-v', '--escape', 'xxx'])
        assert_equals(opts, {'help': True, 'version': True, 'pythonpath': None,
                             'escape': 'xxx', 'argumentfile': None})

    def test_non_list_args(self):
        ap = ArgumentParser('''Options:
 -t --toggle
 -v --value value
 -m --multi multi *
''')
        opts, args = ap.parse_args(())
        assert_equals(opts, {'toggle': False,
                             'value': None,
                             'multi': []})
        assert_equals(args, [])
        opts, args = ap.parse_args(('-t', '-v', 'xxx', '-m', '1', '-m2', 'arg'))
        assert_equals(opts, {'toggle': True,
                             'value': 'xxx',
                             'multi': ['1', '2']})
        assert_equals(args, ['arg'])


class TestDefaultsFromEnvironmentVariables(unittest.TestCase):

    def setUp(self):
        os.environ['ROBOT_TEST_OPTIONS'] = '-t --value default -m1 --multi=2'
        self.ap = ArgumentParser('''Options:
 -t --toggle
 -v --value value
 -m --multi multi *
''', env_options='ROBOT_TEST_OPTIONS')

    def tearDown(self):
        os.environ.pop('ROBOT_TEST_OPTIONS')

    def test_toggle(self):
        opts, args = self.ap.parse_args([])
        assert_equals(opts['toggle'], True)
        opts, args = self.ap.parse_args(['--toggle'])
        assert_equals(opts['toggle'], False)

    def test_value(self):
        opts, args = self.ap.parse_args([])
        assert_equals(opts['value'], 'default')
        opts, args = self.ap.parse_args(['--value', 'given'])
        assert_equals(opts['value'], 'given')

    def test_multi_value(self):
        opts, args = self.ap.parse_args([])
        assert_equals(opts['multi'], ['1', '2'])
        opts, args = self.ap.parse_args(['-m3', '--multi', '4'])
        assert_equals(opts['multi'], ['1', '2', '3', '4'])

    def test_arguments(self):
        os.environ['ROBOT_TEST_OPTIONS'] = '-o opt arg1 arg2'
        ap = ArgumentParser('Usage:\n -o --opt value',
                            env_options='ROBOT_TEST_OPTIONS')
        opts, args = ap.parse_args([])
        assert_equals(opts['opt'], 'opt')
        assert_equals(args, ['arg1', 'arg2'])

    def test_environment_variable_not_set(self):
        ap = ArgumentParser('Usage:\n -o --opt value', env_options='NOT_SET')
        opts, args = ap.parse_args(['arg'])
        assert_equals(opts['opt'], None)
        assert_equals(args, ['arg'])

    def test_non_list_args(self):
        opts, args = self.ap.parse_args(())
        assert_equals(opts, {'toggle': True,
                             'value': 'default',
                             'multi': ['1', '2']})
        assert_equals(args, [])
        opts, args = self.ap.parse_args(('-t', '-v', 'given', '-m3', 'a', 'b'))
        assert_equals(opts, {'toggle': False,
                             'value': 'given',
                             'multi': ['1', '2', '3']})
        assert_equals(args, ['a', 'b'])


class TestArgumentValidation(unittest.TestCase):

    def test_check_args_with_correct_args(self):
        for arg_limits in [None, (1, 1), 1, (1,)]:
            ap = ArgumentParser(USAGE, arg_limits=arg_limits)
            assert_equals(ap.parse_args(['hello'])[1], ['hello'])

    def test_default_validation(self):
        ap = ArgumentParser(USAGE)
        for args in [(), ('1',), ('m', 'a', 'n', 'y')]:
            assert_equals(ap.parse_args(args)[1], list(args))

    def test_check_args_with_wrong_number_of_args(self):
        for limits in [1, (1, 1), (1, 2)]:
            ap = ArgumentParser('usage', arg_limits=limits)
            for args in [(), ('arg1', 'arg2', 'arg3')]:
                assert_raises(DataError, ap.parse_args, args)

    def test_check_variable_number_of_args(self):
        ap = ArgumentParser('usage:  robot.py [options] args', arg_limits=(1,))
        ap.parse_args(['one_is_ok'])
        ap.parse_args(['two', 'ok'])
        ap.parse_args(['this', 'should', 'also', 'work', '!'])
        assert_raises_with_msg(DataError, "Expected at least 1 argument, got 0.",
                               ap.parse_args, [])

    def test_argument_range(self):
        ap = ArgumentParser('usage:  test.py [options] args', arg_limits=(2,4))
        ap.parse_args(['1', '2'])
        ap.parse_args(['1', '2', '3', '4'])
        assert_raises_with_msg(DataError, "Expected 2 to 4 arguments, got 1.",
                               ap.parse_args, ['one is not enough'])

    def test_no_arguments(self):
        ap = ArgumentParser('usage:  test.py [options]', arg_limits=(0, 0))
        ap.parse_args([])
        assert_raises_with_msg(DataError, "Expected 0 arguments, got 2.",
                               ap.parse_args, ['1', '2'])

    def test_custom_validator_fails(self):
        def validate(options, args):
            raise AssertionError
        ap = ArgumentParser(USAGE2, validator=validate)
        assert_raises(AssertionError, ap.parse_args, [])

    def test_custom_validator_return_value(self):
        def validate(options, args):
            return options, [a.upper() for a in args]
        ap = ArgumentParser(USAGE2, validator=validate)
        opts, args = ap.parse_args(['-v', 'value', 'inp1', 'inp2'])
        assert_equals(opts['variable'], 'value')
        assert_equals(args, ['INP1', 'INP2'])


class TestPrintHelpAndVersion(unittest.TestCase):

    def setUp(self):
        self.ap = ArgumentParser(USAGE, version='1.0 alpha')
        self.ap2 = ArgumentParser(USAGE2)

    def test_print_help(self):
        assert_raises_with_msg(Information, USAGE2,
                               self.ap2.parse_args, ['--help'])

    def test_name_is_got_from_first_line_of_the_usage(self):
        assert_equals(self.ap.name, 'Example Tool')
        assert_equals(self.ap2.name, 'Just Name Here')

    def test_name_and_version_can_be_given(self):
        ap = ArgumentParser(USAGE, name='Kakkonen', version='2')
        assert_equals(ap.name, 'Kakkonen')
        assert_equals(ap.version, '2')

    def test_print_version(self):
        assert_raises_with_msg(Information, 'Example Tool 1.0 alpha',
                               self.ap.parse_args, ['--version'])

    def test_print_version_when_version_not_set(self):
        ap = ArgumentParser(' --version', name='Kekkonen')
        msg = assert_raises(Information, ap.parse_args, ['--version'])
        assert_equals(unicode(msg), 'Kekkonen %s' % get_full_version())

    def test_version_is_replaced_in_help(self):
        assert_raises_with_msg(Information, USAGE.replace('<VERSION>', '1.0 alpha'),
                               self.ap.parse_args, ['--help'])

    def test_escapes_are_replaced_in_help(self):
        usage = """Name
 --escape x:y      blaa blaa .............................................. end
                   <-----------------------ESCAPES---------------------------->
                   -- next line --
 --help"""
        expected = """Name
 --escape x:y      blaa blaa .............................................. end
                   Available escapes: amp (&), apos ('), at (@), bslash (\),
                   colon (:), comma (,), curly1 ({), curly2 (}), dollar ($),
                   exclam (!), gt (>), hash (#), lt (<), paren1 ((), paren2
                   ()), percent (%), pipe (|), quest (?), quot ("), semic (;),
                   slash (/), space ( ), square1 ([), square2 (]), star (*)
                   -- next line --
 --help"""
        assert_raises_with_msg(Information, expected,
                               ArgumentParser(usage).parse_args, ['--help'])


if __name__ == "__main__":
    unittest.main()
