from sisyphus.job import Job
from sisyphus.task import Task
from sisyphus import tk

import i6_core.util as util

import os, h5py


class SearchTakeBestRescore(Job):
    """
    Given an n-best list file generated by some model A, and hdf scores for each hyp in the n-best list
    generated by some model B, combine both scores and take the best.
    The scores should be in log-space.
    """

    def __init__(
        self,
        search_py_output: tk.Path,
        hdf_scores_filename: tk.Path,
        scale1: float,
        scale2: float,
        output_gzip: bool = False,
    ):
        """
        :param search_py_output: RETURNN search output py file
        :param hdf_scores_filename: HDF file containing n-best scores
        :param scale1: scale for model 1
        :param scale2: scale for model 2
        :param output_gzip: if set to True, gzip the output
        """

        self.search_py_output = search_py_output
        self.hdf_scores_filename = hdf_scores_filename
        self.scale1 = scale1
        self.scale2 = scale2

        self.out_best_search_results = self.output_path("best_search_results.py" + (".gz" if output_gzip else ""))

    def tasks(self):
        yield Task("run", rqmt={"cpu": 1, "mem": 1, "time": 0.5})

    def get_hdf_hyp_scores(self):
        import h5py

        f = h5py.File(self.hdf_scores_filename, "r")
        scores = f["inputs"]  # [B,Beam]
        tags = f["seqTags"].asstr()  # [B]
        res = {tag: scores[i] for i, tag in enumerate(tags)}  # [str -> List[float]]
        return res

    def run(self):
        hdf_hyp_scores = self.get_hdf_hyp_scores()
        d = eval(util.uopen(self.search_py_output, "rt").read())
        assert isinstance(d, dict)  # seq_tag -> bpe string
        assert not os.path.exists(self.out_best_search_results.get_path())
        with util.uopen(self.out_best_search_results, "wt") as out:
            out.write("{\n")
            for seq_tag, entry in d.items():
                assert isinstance(entry, list)
                # n-best list as [(score, text), ...]
                hdf_scores = hdf_hyp_scores[seq_tag]  # [Beam]
                assert len(entry) == len(hdf_scores)
                # log-prob
                new_entry = [
                    (score * self.scale1 + hdf_scores[i] * self.scale2, text) for i, (score, text) in enumerate(entry)
                ]
                best_score, best_entry = max(new_entry)
                out.write("%r: %r,\n" % (seq_tag, best_entry))
            out.write("}\n")
