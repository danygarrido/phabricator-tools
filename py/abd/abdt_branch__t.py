"""Test suite for abdt_branch."""
#==============================================================================
#                                   TEST PLAN
#------------------------------------------------------------------------------
# Here we detail the things we are concerned to test and specify which tests
# cover those concerns.
#
# Concerns:
# [ B] can test is_abandoned, is_null, is_new
# [ C] can move between all states without error
# [  ] can detect if review branch has new commits (after ff, merge, rebase)
# [  ] can get author names and emails from branch
# [  ] raise if get author names and emails from branch with no history
# [  ] raise if get author names and emails from branch with invalid base
# [  ] can 'get_any_author_emails', raise if no emails ever
# [  ] bad unicode chars in diffs
# [  ] XXX: withReservedBranch
# [  ] XXX: emptyMergeWorkflow
# [  ] XXX: mergeConflictWorkflow
# [  ] XXX: changeAlreadyMergedOnBase
# [  ] XXX: commandeeredLand
# [  ] XXX: createHugeReview
# [  ] XXX: hugeUpdateToReview
# [  ] XXX: empty repository, no history
# [  ] XXX: landing when origin has been updated underneath us
# [  ] XXX: moving tracker branches when there's something in the way
#------------------------------------------------------------------------------
# Tests:
# [ A] test_A_Breathing
# [ B] test_B_UntrackedBranch
# [ C] test_C_MoveBetweenAllMarkedStates
# [ D] test_D_HasNewCommits
#==============================================================================

import os
import shutil
import tempfile
import unittest

import phlgit_push
import phlsys_git

import abdt_branch
import abdt_git
import abdt_gittypes
import abdt_naming


class Test(unittest.TestCase):

    def __init__(self, data):
        super(Test, self).__init__(data)
        self.repo_central = None
        self.repo_dev = None
        self.clone_arcyd = None

    def setUp(self):
        self.repo_central = phlsys_git.GitClone(tempfile.mkdtemp())
        self.repo_dev = phlsys_git.GitClone(tempfile.mkdtemp())
        self.clone_arcyd = abdt_git.Clone(tempfile.mkdtemp(), 'origin')

        self.repo_central.call("init", "--bare")

        self.repo_dev.call("init")
        self.repo_dev.call(
            "remote", "add", "origin", self.repo_central.working_dir)

        self.clone_arcyd.call("init")
        self.clone_arcyd.call(
            "remote", "add", "origin", self.repo_central.working_dir)

    def test_A_Breathing(self):
        pass

    def test_B_UntrackedBranch(self):
        base, branch_name, branch = self._setup_for_untracked_branch()

    def test_C_MoveBetweenAllMarkedStates(self):
        base, branch_name, branch = self._setup_for_untracked_branch()

        next_rev_id = [0]
        rev_id = [None]

        def ok_new_review():
            rev_id[0] = next_rev_id[0]
            next_rev_id[0] += 1
            branch.mark_ok_new_review(rev_id[0])
            self._assert_branch_ok_in_review(
                branch, branch_name, base, rev_id[0])

        def bad_new_in_review():
            rev_id[0] = next_rev_id[0]
            next_rev_id[0] += 1
            branch.mark_new_bad_in_review(rev_id[0])
            self._assert_branch_bad_in_review(
                branch, branch_name, base, rev_id[0])

        def bad_pre_review():
            rev_id[0] = None
            branch.mark_bad_pre_review()
            self._assert_branch_bad_pre_review(
                branch, branch_name, base, rev_id[0])

        def bad_in_review():
            branch.mark_bad_in_review()
            self._assert_branch_bad_in_review(
                branch, branch_name, base, rev_id[0])

        def ok_in_review():
            branch.mark_ok_in_review()
            self._assert_branch_ok_in_review(
                branch, branch_name, base, rev_id[0])

        def bad_land():
            branch.mark_bad_land()
            self._assert_branch_bad_land(branch, branch_name, base, rev_id[0])

        initial_states = [ok_new_review, bad_new_in_review, bad_pre_review]
        transitions = [bad_in_review, ok_in_review, bad_land]

        for initial in initial_states:
            for transition1 in transitions:
                for transition2 in transitions:
                    initial()
                    print rev_id[0]
                    transition1()
                    transition2()
                    # print '', initial.__name__
                    # print '', transition1.__name__
                    # print '', transition2.__name__

    def _create_new_file(self, repo, filename):
        open(os.path.join(repo.working_dir, filename), 'a').close()

    def _setup_for_untracked_branch(self):
        self._create_new_file(self.repo_dev, 'README')
        self.repo_dev.call('add', 'README')
        self.repo_dev.call('commit', '-m', 'initial commit')
        phlgit_push.push(self.repo_dev, 'master', 'origin')

        base = 'master'
        description = 'untracked'

        branch_name = abdt_naming.makeReviewBranchName(description, base)
        self.repo_dev.call('checkout', '-b', branch_name)
        phlgit_push.push(self.repo_dev, branch_name, 'origin')

        self.clone_arcyd.call('fetch', 'origin')
        review_branch = abdt_naming.makeReviewBranchFromName(branch_name)
        review_branch = abdt_gittypes.makeGitReviewBranch(
            review_branch, 'origin')
        branch = abdt_branch.ReviewTrackingBranchPair(
            self.clone_arcyd, review_branch, None, None)

        self._assert_branch_is_new(branch, branch_name, base)

        # should not raise
        branch.verify_review_branch_base()

        return base, branch_name, branch

    def _assert_branch_is_new(self, branch, branch_name, base):
        self.assertIs(branch.is_abandoned(), False)
        self.assertIs(branch.is_null(), False)
        self.assertIs(branch.is_new(), True)
        self.assertIs(branch.is_status_bad_pre_review(), False)
        self.assertIs(branch.is_status_bad_land(), False)
        self.assertIs(branch.is_status_bad(), False)
        self.assertIs(branch.has_new_commits(), True)
        self.assertEqual(branch.base_branch_name(), base)
        self.assertEqual(branch.review_branch_name(), branch_name)
        self.assertIsNone(branch.review_id_or_none())

    def _assert_branch_bad_pre_review(self, branch, branch_name, base, rev_id):
        self.assertIs(branch.is_status_bad_pre_review(), True)
        self.assertIs(branch.is_status_bad_land(), False)
        self.assertIs(branch.is_status_bad(), True)
        self._assert_branch_is_active(branch, branch_name, base, rev_id)

    def _assert_branch_bad_in_review(self, branch, branch_name, base, rev_id):
        self.assertIs(branch.is_status_bad_pre_review(), False)
        self.assertIs(branch.is_status_bad_land(), False)
        self.assertIs(branch.is_status_bad(), True)
        self._assert_branch_is_active(branch, branch_name, base, rev_id)

    def _assert_branch_bad_land(self, branch, branch_name, base, rev_id):
        self.assertIs(branch.is_status_bad_pre_review(), False)
        self.assertIs(branch.is_status_bad_land(), True)
        self.assertIs(branch.is_status_bad(), True)
        self._assert_branch_is_active(branch, branch_name, base, rev_id)

    def _assert_branch_ok_in_review(self, branch, branch_name, base, rev_id):
        self.assertIs(branch.is_status_bad_pre_review(), False)
        self.assertIs(branch.is_status_bad_land(), False)
        self.assertIs(branch.is_status_bad(), False)
        self._assert_branch_is_active(branch, branch_name, base, rev_id)

    def _assert_branch_is_active(self, branch, branch_name, base, rev_id):
        self.assertIs(branch.is_abandoned(), False)
        self.assertIs(branch.is_null(), False)
        self.assertIs(branch.is_new(), False)
        self.assertEqual(branch.base_branch_name(), base)
        self.assertEqual(branch.review_branch_name(), branch_name)
        if rev_id is None:
            self.assertIsNone(branch.review_id_or_none())
        else:
            self.assertEqual(branch.review_id_or_none(), rev_id)

    def tearDown(self):
        shutil.rmtree(self.repo_central.working_dir)
        shutil.rmtree(self.repo_dev.working_dir)
        shutil.rmtree(self.clone_arcyd.working_dir)

#------------------------------------------------------------------------------
# Copyright (C) 2012 Bloomberg L.P.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.
#------------------------------- END-OF-FILE ----------------------------------
