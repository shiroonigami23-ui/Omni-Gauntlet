# omni-receiver

Host-side receiver for the Omni-Gauntlet glove. See the main repository README for full documentation.

```bash
pip install -e ".[control,dev]"
omni-receiver keygen                 # create a shared pairing key
omni-receiver run                    # listen for the glove and control this computer
omni-receiver simulate --dry-run     # no glove needed: scripted gestures, actions printed only
pytest
```
