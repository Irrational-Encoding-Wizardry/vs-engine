vs-engine
=========

An engine for vapoursynth previewers, renderers and script analyis tools.

Installing
----------

``` 
pip install vsengine
```

The latest development version can be downloaded from the github-actions tab.
Install the included .whl-file.

Using vsengine
--------------

Look at this example:
```py
import vapoursynth as vs
from vsengine.vpy import script

script("/script/to/my.vpy").result()
vs.get_output(0).output()
```

Development
-----------

Install the dependencies listed in `pyproject.toml` as well as `flit`.

For convenience,
the included nix-flake contains dev-shells with different python and vapoursynth versions preconfigured.

Running Tests
-------------

You can run tests with this command:

```
python -m unittest discover -s ./tests
```

For users with Nix installed,
the included flake contains tests for specific vs and python versions.
These can be run by running `nix flake check`.

Contributing
------------

Users might want to bring their own versions of vapoursynth related plugins and libraries.
Depending on any of them would thus be of disservice to the user.
This is the reason why depending on any plugin or library is banned in this project.
The only exception is when this dependency is optional,
meaning that the feature in question does not lose any functionality when the dependency is missing.
In any case,
the addition of new dependencies (optional or otherwise) must be coordinated with the maintainer prior to filing a PR.

This project is licensed under the EUPL-1.2.
When contributing to this project you accept that your code will be using this license.
By contributing you also accept any relicencing to newer versions of the EUPL at a later point in time.

Your commits have to be signed with a key registered with GitHub.com at the time of the merge.

