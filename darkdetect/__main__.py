# -----------------------------------------------------------------------------
#  Copyright (C) 2019 Alberto Sottile
#
#  Distributed under the terms of the 3-clause BSD License.
# -----------------------------------------------------------------------------

"""Print the current OS theme."""

import darkdetect

print(f"Current theme: {darkdetect.theme()}")
