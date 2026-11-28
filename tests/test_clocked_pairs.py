import unittest
from scripts.audit_clocked_pairs import paired_results

class ClockedPairs(unittest.TestCase):
    def test_reconcile_by_game_id_not_finish_order(self):
        rows=["Finished game 4 (Main vs New): 1-0 {White mates}",
              "Finished game 2 (Main vs New): 0-1 {Black mates}",
              "Finished game 1 (New vs Main): 1/2-1/2 {Draw}",
              "Finished game 3 (New vs Main): 0-1 {Black mates}",
              "Ptnml(0-2): [1, 0, 0, 1, 0], WL/DD Ratio: inf"]
        r=paired_results(rows)
        self.assertEqual(r["pentanomial"],[1,0,0,1,0])
        self.assertEqual(r["candidate_loss_draw_win_by_color"],{"white":[1,1,0],"black":[1,0,1]})
        for bad in (rows[1:],rows+[rows[0]],rows[:-1],rows[:-1]+["Ptnml(0-2): [0,2,0,0,0]"],
                    [rows[0].replace("Main vs New","New vs Main")]+rows[1:]):
            with self.assertRaises(ValueError): paired_results(bad)
