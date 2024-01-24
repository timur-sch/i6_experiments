"""
Data to store globally to make it easier to transfer arbitrarily between the different experiments
"""
from dataclasses import dataclass
from sisyphus import tk
from typing import Any, Dict

synthetic_ogg_zip_data = {}
synthetic_bliss_data = {}


def add_synthetic_data(name: str, ogg_zip: tk.Path, bliss: tk.Path):
    global synthetic_ogg_zip_data
    global synthetic_bliss_data
    assert name not in synthetic_ogg_zip_data.keys()
    synthetic_ogg_zip_data[name] = ogg_zip
    synthetic_bliss_data[name] = bliss
    
duration_alignments = {}

def add_duration(name: str, duration_hdf: tk.Path):
    global duration_alignments
    assert name not in duration_alignments.keys()
    duration_alignments[name] = duration_hdf

@dataclass
class VocoderPackage:
    checkpoint: tk.Path
    config: Dict[str, Any]

vocoders: Dict[str, VocoderPackage] = {}

def add_vocoder(name: str, vocoder: VocoderPackage):
    global vocoders
    assert name not in vocoders.keys()
    vocoders[name] = vocoder


ctc_models: Dict[str, tk.Path] = {}

def add_ctc_model(name: str, checkpoint: tk.Path):
    global ctc_models
    assert name not in ctc_models.keys()
    ctc_models[name] = checkpoint
