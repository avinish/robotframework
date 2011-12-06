import unittest
from os.path import abspath, dirname, join

from robot.utils.asserts import assert_equals
from robot.result import TestSuite, TestCase, Keyword, Message
from robot.model import Statistics
from robot.reporting.jsmodelbuilders import *
from robot.reporting.parsingcontext import TextIndex as StringIndex

CURDIR = dirname(abspath(__file__))


def get_status(*elements):
    return elements if elements[-1] else elements[:-1]

def remap_model(model, strings):
    for item in model:
        if isinstance(item, StringIndex):
            yield strings[item][1:]
        elif isinstance(item, (int, long, type(None))):
            yield item
        elif isinstance(item, tuple):
            yield tuple(remap_model(item, strings))
        else:
            raise AssertionError("Item '%s' has invalid type '%s'" % (item, type(item)))


class TestBuildTestSuite(unittest.TestCase):

    def test_default_suite(self):
        self._verify_suite(TestSuite())

    def test_suite_with_values(self):
        suite = TestSuite('', 'Name', 'Doc', {'m1': 'v1', 'm2': 'v2'}, 'Message',
                          '20111204 19:00:00.000', '20111204 19:00:42.001')
        self._verify_suite(suite, 'Name', 'Doc', ('m1', 'v1', 'm2', 'v2'),
                           message='Message', start=0, elapsed=42001)

    def test_relative_source(self):
        self._verify_suite(TestSuite(source='non-existing'), source='non-existing')
        self._verify_suite(TestSuite(source=__file__), source=__file__,
                           relsource=os.path.basename(__file__))

    def test_suite_html_formatting(self):
        self._verify_suite(TestSuite(name='*xxx*', doc='*bold* <&>',
                                     metadata={'*x*': '*b*', '<': '>'}),
                           name='*xxx*', doc='<b>bold</b> &lt;&amp;&gt;',
                           metadata=('*x*', '<b>b</b>', '<', '&gt;'))

    def test_default_test(self):
        self._verify_test(TestCase())

    def test_test_with_values(self):
        test = TestCase('Name', '*Doc*', ['t1', 't2'], '1 minute', 'PASS', 'Msg',
                        '20111204 19:22:22.222', '20111204 19:22:22.333')
        self._verify_test(test, 'Name', '<b>Doc</b>', ('t1', 't2'), 1,
                          '1 minute', 1, 'Msg', 0, 111)

    def test_default_keyword(self):
        self._verify_keyword(Keyword())

    def test_keyword_with_values(self):
        kw = Keyword('Name', 'http://doc', ['a1', 'a2'], 'setup', '1 second', 'PASS',
                     '20111204 19:42:42.000', '20111204 19:42:42.042')
        self._verify_keyword(kw, 1, 'Name', '<a href="http://doc">http://doc</a>',
                             'a1, a2', '1 second', 1, 0, 42)

    def test_default_message(self):
        self._verify_message(Message())

    def test_message_with_values(self):
        msg = Message('Message', 'WARN', timestamp='20111204 22:04:03.210')
        self._verify_message(msg, 'Message', 3, 0)

    def test_message_with_html(self):
        self._verify_message(Message('<img>'), '&lt;img&gt;')
        self._verify_message(Message('<img>', html=True), '<img>')

    def test_nested_structure(self):
        suite = TestSuite()
        suite.set_criticality(critical_tags=['crit'])
        suite.keywords = [Keyword(type='setup'), Keyword(type='teardown')]
        K1 = self._verify_keyword(suite.keywords[0], type=1)
        K2 = self._verify_keyword(suite.keywords[1], type=2)
        suite.suites = [TestSuite()]
        suite.suites[0].tests = [TestCase(tags=['crit', 'xxx'])]
        t = self._verify_test(suite.suites[0].tests[0], tags=('crit', 'xxx'))
        suite.tests = [TestCase(), TestCase(status='PASS')]
        S1 = self._verify_suite(suite.suites[0],
                                status=0, tests=(t,), stats=(1, 0, 1, 0))
        suite.tests[0].keywords = [Keyword(type='for'), Keyword()]
        suite.tests[0].keywords[0].keywords = [Keyword(type='foritem')]
        suite.tests[0].keywords[0].messages = [Message()]
        k = self._verify_keyword(suite.tests[0].keywords[0].keywords[0], type=4)
        m = self._verify_message(suite.tests[0].keywords[0].messages[0])
        k1 = self._verify_keyword(suite.tests[0].keywords[0],
                                  type=3, keywords=(k,), messages=(m,))
        suite.tests[0].keywords[1].messages = [Message(), Message('msg')]
        m1 = self._verify_message(suite.tests[0].keywords[1].messages[0])
        m2 = self._verify_message(suite.tests[0].keywords[1].messages[1], 'msg')
        k2 = self._verify_keyword(suite.tests[0].keywords[1], messages=(m1, m2))
        T1 = self._verify_test(suite.tests[0], critical=0, keywords=(k1, k2))
        T2 = self._verify_test(suite.tests[1], critical=0, status=1)
        self._verify_suite(suite, status=0, keywords=(K1, K2), suites=(S1,),
                           tests=(T1, T2), stats=(3, 1, 1, 0))

    def test_timestamps(self):
        suite = TestSuite(starttime='20111205 00:33:33.333')
        suite.keywords.create(starttime='20111205 00:33:33.334')
        suite.keywords[0].messages.create('Message', timestamp='20111205 00:33:33.343')
        suite.keywords[0].messages.create(level='DEBUG', timestamp='20111205 00:33:33.344')
        suite.tests.create(starttime='20111205 00:33:34.333')
        builder = JsModelBuilder()
        model = builder._build_suite(suite)
        self._verify_status(model[5], start=0)
        self._verify_status(model[-2][0][5], start=1)
        self._verify_mapped(model[-2][0][-1], builder._context.strings,
                            ((10, 2, 'Message'), (11, 1, '')))
        self._verify_status(model[-3][0][5], start=1000)

    def _verify_status(self, model, status=0, start=None, elapsed=0):
        assert_equals(model, (status, start, elapsed))

    def _verify_suite(self, suite, name='', doc='', metadata=(), source='',
                      relsource='', status=1, message='', start=None, elapsed=0,
                      suites=(), tests=(), keywords=(), stats=(0, 0, 0, 0)):
        return self._build_and_verify('suite', suite, name, source, relsource,
                                      doc, metadata,
                                      get_status(status, start, elapsed, message),
                                      suites, tests, keywords, stats)

    def _verify_test(self, test, name='', doc='', tags=(), critical=1, timeout='',
                     status=0, message='', start=None, elapsed=0, keywords=()):
        return self._build_and_verify('test', test, name, timeout, critical, doc, tags,
                                      get_status(status, start, elapsed, message),
                                      keywords)

    def _verify_keyword(self, keyword, type=0, name='', doc='', args='',  timeout='',
                        status=0, start=None, elapsed=0, keywords=(), messages=()):
        return self._build_and_verify('keyword', keyword, type, name, timeout,
                                      doc, args, (status, start, elapsed),
                                      keywords, messages)

    def _verify_message(self, msg, message='', level=2, timestamp=None):
        return self._build_and_verify('message', msg, timestamp, level, message)

    def _build_and_verify(self, type, item, *expected):
        builder = JsModelBuilder(log_path=join(CURDIR, 'log.html'))
        model = getattr(builder, '_build_'+type)(item)
        self._verify_mapped(model, builder._context.strings, expected)
        return expected

    def _verify_mapped(self, model, strings, expected):
        mapped_model = tuple(remap_model(model, strings))
        assert_equals(mapped_model, expected)


class TestSplitting(unittest.TestCase):

    def test_test_keywords(self):
        suite = self._get_suite_with_tests()
        expected, _ = self._build_and_remap(suite)
        expected_split = [expected[-3][0][-1], expected[-3][1][-1]]
        expected[-3][0][-1], expected[-3][1][-1] = 1, 2
        model, builder = self._build_and_remap(suite, split_log=True)
        assert_equals(builder._context.strings, ['*', '*suite', '*t1', '*t2'])
        assert_equals(model, expected)
        assert_equals([strings for _, strings in builder._split_results],
                      [['*', '*t1-k1', '*t1-k1-k1', '*t1-k2'], ['*', '*t2-k1']])
        assert_equals([self._to_list(remap_model(*res)) for res in builder._split_results],
                      expected_split)

    def _get_suite_with_tests(self):
        suite = TestSuite(name='suite')
        suite.tests = [TestCase('t1'), TestCase('t2')]
        suite.tests[0].keywords = [Keyword('t1-k1'), Keyword('t1-k2')]
        suite.tests[0].keywords[0].keywords = [Keyword('t1-k1-k1')]
        suite.tests[1].keywords = [Keyword('t2-k1')]
        return suite

    def _build_and_remap(self, suite, split_log=False):
        builder = JsModelBuilder(split_log=split_log)
        model = remap_model(builder._build_suite(suite), builder._context.strings)
        return self._to_list(model), builder

    def _to_list(self, model):
        return list(self._to_list(item) if isinstance(item, tuple) else item
                    for item in model)

    def test_suite_keywords(self):
        suite = self._get_suite_with_keywords()
        expected, _ = self._build_and_remap(suite)
        expected_split = [expected[-2][0][-2], expected[-2][1][-2]]
        expected[-2][0][-2], expected[-2][1][-2] = 1, 2
        model, builder = self._build_and_remap(suite, split_log=True)
        assert_equals(builder._context.strings, ['*', '*root', '*k1', '*k2'])
        assert_equals(model, expected)
        assert_equals([strings for _, strings in builder._split_results],
                     [['*', '*k1-k2'], ['*']])
        assert_equals([self._to_list(remap_model(*res)) for res in builder._split_results],
                      expected_split)

    def _get_suite_with_keywords(self):
        suite = TestSuite(name='root')
        suite.keywords = [Keyword('k1', type='setup'), Keyword('k2', type='teardown')]
        suite.keywords[0].keywords = [Keyword('k1-k2')]
        return suite

    def test_nested_suite_and_test_keywords(self):
        suite = self._get_nested_suite_with_tests_and_keywords()
        expected, _ = self._build_and_remap(suite)
        expected_split = [expected[-4][0][-3][0][-1], expected[-4][0][-3][1][-1],
                          expected[-4][1][-3][0][-1], expected[-4][1][-2][0][-2],
                          expected[-2][0][-2], expected[-2][1][-2]]
        (expected[-4][0][-3][0][-1], expected[-4][0][-3][1][-1],
         expected[-4][1][-3][0][-1], expected[-4][1][-2][0][-2],
         expected[-2][0][-2], expected[-2][1][-2]) = 1, 2, 3, 4, 5, 6
        model, builder = self._build_and_remap(suite, split_log=True)
        assert_equals(model, expected)
        assert_equals([self._to_list(remap_model(*res)) for res in builder._split_results],
                      expected_split)

    def _get_nested_suite_with_tests_and_keywords(self):
        suite = self._get_suite_with_keywords()
        sub = TestSuite(name='suite2')
        suite.suites = [self._get_suite_with_tests(), sub]
        sub.keywords.create('kw', type='setup')
        sub.keywords[0].keywords.create('skw')
        sub.keywords[0].keywords[0].messages.create('Message')
        sub.tests.create('test', doc='tdoc')
        sub.tests[0].keywords.create('koowee', doc='kdoc')
        return suite


class TestBuildStatistics(unittest.TestCase):

    def test_total_stats(self):
        critical, all = self._build_statistics()[0]
        self._verify_stat(critical, 2, 0, 'Critical Tests')
        self._verify_stat(all, 2, 2, 'All Tests')

    def test_tag_stats(self):
        t2, comb, t1 = self._build_statistics()[1]
        self._verify_stat(t2, 2, 0, 't2', info='critical', doc='doc', links='t:url')
        self._verify_stat(comb, 2, 0, 'name', info='combined', combined='t1&t2')
        self._verify_stat(t1, 2, 2, 't1')

    def test_suite_stats(self):
        root, sub1, sub2 = self._build_statistics()[2]
        self._verify_stat(root, 2, 2, 'root', name='root', id='s1')
        self._verify_stat(sub1, 1, 1, 'root.sub1', name='sub1', id='s1-s1')
        self._verify_stat(sub2, 1, 1, 'root.sub2', name='sub2', id='s1-s2')

    def _build_statistics(self):
        return JsModelBuilder()._build_statistics(self._get_statistics())

    def _get_statistics(self):
        return Statistics(self._get_suite(),
                          suite_stat_level=2,
                          tag_stat_combine=[('t1&t2', 'name')],
                          tag_doc=[('t2', 'doc')],
                          tag_stat_link=[('?2', 'url', '%1')])

    def _get_suite(self):
        suite = TestSuite(name='root')
        suite.set_criticality(critical_tags=['t2'])
        sub1 = TestSuite(name='sub1')
        sub2 = TestSuite(name='sub2')
        suite.suites = [sub1, sub2]
        sub1.tests = [TestCase(tags=['t1', 't2'], status='PASS'),
                      TestCase(tags=['t1'], status='FAIL')]
        sub2.tests.create(tags=['t1', 't2'], status='PASS')
        sub2.suites.create(name='below suite stat level')
        sub2.suites[0].tests.create(tags=['t1'], status='FAIL')
        return suite

    def _verify_stat(self, stat, pass_, fail, label, **attrs):
        attrs.update({'pass': pass_, 'fail': fail, 'label': label})
        assert_equals(stat, attrs)


if __name__ == '__main__':
    unittest.main()