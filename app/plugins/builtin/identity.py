"""Plugin für Identitätsnachweise.

Die Ausweistypen sind bewusst nicht als Enum im Kern hinterlegt, sondern
kommen aus einem Plugin – ein weiterer Typ (z. B. „Firmenausweis") ist eine
Zeile in :meth:`IdentityPlugin.id_document_types`.
"""

from __future__ import annotations

from typing import Sequence

from ..api import IdDocumentType, RentalPlugin


class IdentityPlugin(RentalPlugin):
    key = "identity"
    name = "Identitätsnachweise"
    description = "Stellt die unterstützten Ausweistypen bereit."

    def id_document_types(self) -> Sequence[IdDocumentType]:
        return (
            IdDocumentType("id_card", "Personalausweis"),
            IdDocumentType("passport", "Reisepass"),
            IdDocumentType("drivers_license", "Führerschein"),
            IdDocumentType("student_card", "Studentenausweis"),
        )


PLUGIN = IdentityPlugin()
