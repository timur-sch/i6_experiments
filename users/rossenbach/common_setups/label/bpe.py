"""
Contains helper functions for the legacy BPE pipeline

This pipeline is compatible with old BPE setups, and thus with (probably all) of Kazukis trained LMs
"""
from dataclasses import dataclass
from functools import lru_cache
import os
import typing

from sisyphus import tk

from i6_core.bpe.train import ReturnnTrainBpeJob
from i6_core.corpus.convert import CorpusToTxtJob
from i6_core.tools.git import CloneGitRepositoryJob


@dataclass(frozen=True)
class BPESettings:
    """
    Dataclass managing setting variables for BPE. Do not create by hand but use `get_bpe_settings`
    unless for debugging purposes.
    """
    bpe_codes: tk.Path
    bpe_vocab: tk.Path
    bpe_vocab_size: tk.Variable
    unk_label: typing.Optional[str]


@lru_cache()
def get_returnn_subword_nmt(commit_hash, output_prefix=""):
    """
    clones the legacy subword-nmt reposity from "albertz" and returns the path

    :param str commit_hash:
    :return: subword-nmt repo path
    :rtype tk.Path
    """
    subword_nmt_job = CloneGitRepositoryJob(
        url="https://github.com/albertz/subword-nmt",
        commit=commit_hash,
        checkout_folder_name="subword-nmt",
    )
    subword_nmt_job.add_alias(os.path.join(output_prefix, "clone_subword_nmt"))
    tk.register_output(os.path.join(output_prefix, "subword-nmt-repo"), subword_nmt_job.out_repository)

    return subword_nmt_job.out_repository


@lru_cache()
def get_bpe_settings(bliss_corpus, bpe_size, subword_nmt_repo_path, unk_label="UNK", output_prefix=""):
    """
    Creates a BPESettings object containing codec and vocab files based on the provided parameters.

    As this helper is targeted for ASR, it directly accepts a bliss_corpus as input for the BPE estimation

    :param Path bliss_corpus: bliss corpus xml as training data for the BPE estimation
    :param int bpe_size: size of the BPE merge operations
    :param Path subword_nmt_repo_path: path to the subword_nmt_repo, can be filled with the result of `get_returnn_subword_nmt`
    :param str unk_label: unknown label, this should in most cases only be used for training, but maybe someone needs it.
    :param str output_prefix: set output_prefix to activate alias and output registration
    :return: Filled BPESettings object
    :rtype: BPESettings
    """
    to_text_job = CorpusToTxtJob(bliss_corpus)
    to_text_job.add_alias(os.path.join(output_prefix, "bliss_to_text"))

    train_bpe_job = ReturnnTrainBpeJob(
        text_file=to_text_job.out_txt,
        bpe_size=bpe_size,
        unk_label=unk_label,
        subword_nmt_repo=subword_nmt_repo_path)

    if output_prefix:
        train_bpe_job.add_alias(os.path.join(output_prefix, "train_bpe"))

        tk.register_output(os.path.join(output_prefix, "bpe.codes"), train_bpe_job.out_bpe_codes)
        tk.register_output(os.path.join(output_prefix, "bpe.vocab"), train_bpe_job.out_bpe_vocab)
        tk.register_output(os.path.join(output_prefix, "bpe.vocab.size"), train_bpe_job.out_vocab_size)
