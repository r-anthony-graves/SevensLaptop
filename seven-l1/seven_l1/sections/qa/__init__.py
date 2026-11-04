"""QA (piece 5): the web's QA desk over the active project's qa/<slug>/
package, generation through /v1/pm/author, and qa task dispatch."""

from __future__ import annotations


def build_qa_section(active):
    from seven_l1.sections import Section
    from seven_l1.sections.pm.client import PmClient
    from seven_l1.sections.qa.client import QaClient
    from seven_l1.sections.qa.panel import QaPanel
    from seven_l1.workspace.files import FilesClient

    qa, pm, files = QaClient(), PmClient(), FilesClient()
    panel = QaPanel(qa, pm, files, active)
    for client in (qa, pm, files):
        client.setParent(panel)
    return Section("QA", panel, stop=panel.stop_clients)
