import gitlab
import time
from datetime import date
from datetime import datetime
import sys

DEFAULT_BRANCH = 'master'

CHANGELOG_START_DATE = '2020-01-01T00:00:00.000Z'


class ChangeLogGenerator(object):
    MAIN_TEMPLATE='''# CHANGELOG

{releases}'''
    RELEASE_TEMPLATE=\
'''## Release {merge_request}
{changes}'''
    CHANGE_TEMPLATE='''
### Features
{features}
### Bug Fixes
{bugs}
### Other
{no_label}
'''
    CHANGE_ITEM_TEMPLATE='''* {title} ({ref}, {author})'''

    def __init__(self, host, group, project, user=None, password=None, private_token=None, output='CHANGELOG.md'):
        self.host = host
        self.user = user
        self.password = password
        self.private_token = private_token
        self.group = group
        self.project = project
        self.output = output

    @classmethod
    def from_config(cls, config, output='CHANGELOG.md'):
        return ChangeLogGenerator(
            host = config.host,
            private_token = config.private_token,
            group = config.group,
            project = config.project,
            output = output,
        )

    def to_date_time(self, time_str: str):
        return datetime.strptime(time_str, '%Y-%m-%dT%H:%M:%S.%f%z')

    def generate(self):
        gl = gitlab.Gitlab(self.host, private_token=self.private_token)
        pl = gl.projects.list(search=self.project)
        if not pl:
            print("Project %s not found" % self.project)
            return
        print(pl)
        project = None
        for tmp_project in pl:
            if tmp_project.namespace['name'] == self.group and tmp_project.name == self.project:
                project = tmp_project
                break
        if not project:
            print("Project in group %s not found" % self.group)
            return

        # maybe look at commits, then check if merge commit and get mr info
        # loop this until tag commit found

        commits = project.commits.list(all=True,
                                       query_parameters={'ref_name': DEFAULT_BRANCH,
                                                         'since': CHANGELOG_START_DATE})

        tags = project.tags.list()
        num_tags = len(tags)
        print("tags: " + str(num_tags))

        for tag_ch in tags:
            print("tag commit id: " + tag_ch.commit['id'] + ", tag: " + str(tag_ch))
            print(self.to_date_time(tag_ch.commit['created_at']))


        print("commits: " + str(len(commits)))

        tag_changes = [{'tag': tag, 'changes': {'features': [], 'bugs': [], 'no_label': []}} for tag in tags]
        tag_map = {tag['tag'].name : tag for tag in tag_changes}
        #merge_commits = (commit for commit in commits if commit.message.startswith('Merge branch'))
        print(tag_map)

        merge_requests = project.mergerequests.list(all=True, state='merged')
        print("mr's: " + str(len(merge_requests)))

        for i in range(num_tags):
            end_date = self.to_date_time(tags[i].commit['created_at'])
            start_date = end_date

            if i < num_tags-1:
                start_date = self.to_date_time(tags[i+1].commit['created_at'])
            if i == num_tags-1:
                start_date = self.to_date_time(CHANGELOG_START_DATE)
            if i >= num_tags:
                break
            current_tag = tags[i].name
            changes = tag_map[current_tag]['changes']

            for mr in merge_requests:
                merge_time = self.to_date_time(mr.merged_at)
                if start_date <= merge_time <= end_date:
                    if 'feature' in mr.labels:
                        changes['features'].append(mr)
                    elif 'bug' in mr.labels:
                        changes['bugs'].append(mr)
                    else:
                        changes['no_label'].append(mr)

        release_tpl = []
        for tag_ch in tag_changes:
            # Render features
            feats = self.gen_change_item(tag_ch['changes']['features'])
            # Render bugs
            bugs = self.gen_change_item(tag_ch['changes']['bugs'])
            # Render unlabeled
            unlabeled = self.gen_change_item(tag_ch['changes']['no_label'])

            change_tpl = self.CHANGE_TEMPLATE.format(
                features='\n'.join(feats),
                bugs='\n'.join(bugs),
                no_label='\n'.join(unlabeled)
            )
            release_tpl.append(self.RELEASE_TEMPLATE.format(
                merge_request=tag_ch['tag'].name,
                changes=change_tpl,
            ))
        changelog = self.MAIN_TEMPLATE.format(releases='\n'.join(release_tpl))
        with open(self.output, 'w+') as out:
            out.write(changelog)
            print("Changelog is generated to '%s' success." % self.output)

    def gen_change_item(self, changes):
        changes_tpl = []
        for change in changes:
            changes_tpl.append(
                self.CHANGE_ITEM_TEMPLATE.format(
                    title=change.title,
                    ref='[%s](%s)' % (change.reference, change.web_url),
                    author='[%s](%s)' % (change.author['name'], change.author['web_url'] )
                )
            )
        return changes_tpl
