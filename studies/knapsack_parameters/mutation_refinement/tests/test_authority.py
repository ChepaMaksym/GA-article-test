"""Prospective CI fixtures for scope, resources and evidence integrity."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .. import authority as a


class AuthorityTests(unittest.TestCase):
    def test_only_single_registered_technical_markers(self):
        for phase in a.PHASES:
            self.assertEqual(a.phase("Technical [mutation-refinement:"+phase+"]"),phase)
        for text in ("[mutation-refinement:main]","[mutation-refinement:calibrate]",
                     "[mutation-refinement:tests] [other:tests]","unmarked"):
            with self.assertRaises(ValueError):a.phase(text)

    def test_resource_permission_never_inherited(self):
        original=a.read_json(a.MODULE/"resource_authorization.json")
        blocked=deepcopy(original);blocked["technical"]["explicit_user_approval"]=False
        with patch.object(a,"read_json",return_value=blocked):
            with self.assertRaises(ValueError):a.grant_for("tests")
        allowed=deepcopy(original);allowed["technical"]["explicit_user_approval"]=True
        with patch.object(a,"read_json",return_value=allowed):
            self.assertEqual(a.grant_for("tests")["runner_minutes_ceiling"],60)
        allowed["main"]["explicit_user_approval"]=True
        with patch.object(a,"read_json",return_value=allowed):
            with self.assertRaises(ValueError):a.grant_for("tests")

    def test_exact_resource_ceiling_and_unknown_use(self):
        grant={"runner_minutes_ceiling":60}
        a.check_allowance("pilot",{"used_runner_minutes":26},grant)
        for use in (27,None,-1):
            with self.assertRaises(ValueError):a.check_allowance("pilot",{"used_runner_minutes":use},grant)

    def test_manifest_rejects_tamper_missing_and_unlisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sample=root/"sample.json";sample.write_text('{"ok":true}',encoding="utf-8")
            a.write_manifest(root);a.verify_manifest(root)
            sample.write_text('{"ok":false}',encoding="utf-8")
            with self.assertRaises(ValueError):a.verify_manifest(root)
            a.write_manifest(root);sample.unlink()
            with self.assertRaises((ValueError,FileNotFoundError)):a.verify_manifest(root)
            a.write_manifest(root);(root/"extra.txt").write_text("extra",encoding="utf-8")
            with self.assertRaises(ValueError):a.verify_manifest(root)

    def test_evidence_paths_stay_in_their_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            for path in ("../outside","/absolute","C:/outside","nested\\outside"):
                with self.assertRaises(ValueError):a.safe_child(tmp,path)

    def test_prepared_clones_are_not_deduplicated(self):
        from ..driver import _initial_masks
        condition={"task_index":0,"start_index":0,"start":"cloned"}
        masks,before,after=_initial_masks(condition,"0"*100)
        self.assertEqual(masks,["0"*100]*30)
        self.assertEqual(before,after)
