"""ATS adapter protocol.

Each adapter fetches current postings for one employer from its ATS and
returns them as raw, unscored :class:`~catalyst.models.Posting` objects —
classification (sector confirmation, level, score, tags) happens later, in
``catalyst.classify``.
"""
from __future__ import annotations

from typing import List, Protocol

from ..models import Employer, Posting


class Adapter(Protocol):
    def fetch(self, employer: Employer) -> List[Posting]:
        """Return current postings for *employer*, or ``[]`` on failure.

        An adapter must never raise for a single bad employer — log and
        return an empty list so one broken employer can't take down a run
        across all employers.
        """
        ...
