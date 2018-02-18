#!/usr/bin/env python2.7

"""
Outputs a DOT/graphviz digraph with vertices
being issues of the selected component that
block High or Highest priority or Major severity
issues of other components.

Sample usage:
./jirablockers.py <user> <server> <project> <component> \
| neato -Tpdf -o blockers.pdf
"""

import sys
import getpass

from jira import JIRA


def resolved(issue):
    """Is the issue resolved?"""
    return issue.fields.status.name in ['Done', 'Resolved', 'Fertig', 'Closed']


def components(issue):
    """Get the component names of an issue"""
    if hasattr(issue.fields, 'components'):
        return [component.name for component in issue.fields.components]
    return []


def relevant(issue, component):
    """Select relevant issues: those that block issues
    of other components that are either High or Highest
    priority or Major severity. Intended as customizable."""
    if resolved(issue):
        return False
    if component in components(issue):
        return False
    return (issue.fields.priority.name in ["High", "Highest"] or
            (hasattr(issue.fields, "severity") and
             issue.fields.severity.name in ["Major"]))


def node(issue, special=False):
    """Format a graph vertex as default or
    triangle if special (i.e. blocking)."""
    fmt = '"{}" '
    if special:
        fmt += "[ shape = triangle ]"
    return fmt.format(issue)


def output(blocked):
    """Output DOT digraph with edges representing 'is-blocked-by'."""
    print('''digraph blockers {
             layout=neato;
             overlap=false;
             sep="+1";''')
    for issue, blocked_info in blocked.iteritems():
        special = not blocked_info['is-blocked-by']
        if special:
            print('{}'.format(node(issue, special)))
        for out_issue in blocked_info["blocks"]:
            print('{}'.format(node(out_issue)))
            print('{} -> {};'.format(node(issue), node(out_issue)))
#        for in_issue in blocked_info["is-blocked-by"]:
#            print '"{}" -> "{}";'.format(in_issue, issue)
    print('}')


def get_issue(key, issues):
    """Get the issue with a certain key"""
    return filter((lambda issue: issue.key == key), issues)[0]


def get_blocked(check_issues, all_issues, component):
    """Return a dictionary of blocking information,
    with the blocking issue's key as key and a dict
    of blocked and blocking issues."""
    blocked = {}
    for issue in check_issues:
        if resolved(issue):
            continue
        outward_issues = []
        inward_issues = []
        for link in issue.fields.issuelinks:
            if link.type.name == 'Blocks':
                if hasattr(link, 'outwardIssue'):
                    outward_issue = get_issue(link.outwardIssue.key, all_issues)
                    if outward_issue in check_issues:
                        continue
                    if relevant(outward_issue, component):
                        outward_issues.append(outward_issue.key)
                if hasattr(link, 'inwardIssue'):
                    inward_issue = get_issue(link.inwardIssue.key, all_issues)
                    if relevant(inward_issue, None):
                        inward_issues.append(inward_issue.key)
        if outward_issues:
            blocked[issue.key] = \
                {'blocks': outward_issues, 'is-blocked-by': inward_issues}
    return blocked


class JIRAWrap(JIRA):
    """Wrapper around JIRA class with extra
    utilities for the current use-case."""

    MAX_ISSUES = 1000

    def __init__(self, user, password, **options):
        super(JIRAWrap, self).__init__(options, basic_auth=(user, password))

    def issues_chunk(self, query, start_at=0, max_results=50):
        """Retrieve a chunk of component/project issues (1000 hard-coded max)."""
        return [self.issue(issue) for issue in self.search_issues(
            query,
            start_at,
            max_results)]

    def component_issues(self, project, component=None):
        """Retrieve all issues of the specified component and project."""
        issues = []
        counter = 0
        inc = JIRAWrap.MAX_ISSUES
        query = 'project={}'.format(project)
        if component is not None:
            query += ' AND component={}'.format(component)
        print('# JQL: {}'.format(query))
        while True:
            new_issues = self.issues_chunk(query, counter, inc)
            issues += new_issues
            break
            if len(new_issues) < inc:
                break
            counter += inc
        print('# Found {} matching issues.'.format(len(issues)))
        return issues


def run(jira, project, component):
    """Main method: output digraph of blocking issues."""
    all_issues = jira.component_issues(project) + jira.component_issues('TFAPD')
    issues_to_check = jira.component_issues(project, component)
    print("# {} in {}".format(len(issues_to_check), component))
    output(get_blocked(issues_to_check, all_issues, component))


def usage():
    """Print usage and exit because of error."""
    print('{} <user> <server> <project> <component>'.format(sys.argv[0]))
    exit(42)


if __name__ == "__main__":
    if len(sys.argv) < 4:
        usage()
    USER = sys.argv[1]
    SERVER = sys.argv[2]
    OPTIONS = {'server': SERVER}
    PROJECT = sys.argv[3]
    COMPONENT = None
    if len(sys.argv) == 5:
        COMPONENT = '"{}"'.format(sys.argv[4])
    PASSWORD = getpass.getpass()
    JIRA = JIRAWrap(USER, PASSWORD, **OPTIONS)
    run(JIRA, PROJECT, COMPONENT)
