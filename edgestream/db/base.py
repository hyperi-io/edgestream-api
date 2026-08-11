# edgestream/core/db/base.py

# Import all ORM models so they are registered with Base’s metadata before Alembic, etc.
from edgestream.models.system.advanced_setting import AdvancedSetting  # noqa: F401
from edgestream.models.system.task import Task  # noqa: F401
from edgestream.models.system.log_viewer import LogViewer  # noqa: F401
from edgestream.models.system.system import System  # noqa: F401
from edgestream.models.system.user import User  # noqa: F401
from edgestream.models.system.certificate_store import Certificate  # noqa: F401

from edgestream.models.network.dns_client import DNS  # noqa: F401# a: F401
from edgestream.models.network.dns_forwarder import DNSForwarder  # noqa: F401# a: F401
from edgestream.models.network.ip_management import IPManagement  # noqa: F401# a: F401
from edgestream.models.network.ntp_client import NTP  # noqa: F401# a: F401
from edgestream.models.network.static_host import StaticHost  # noqa: F401# a: F401
from edgestream.models.network.static_route import StaticRoute  # noqa: F401# a: F401

from edgestream.models.event.transform import Transform  # noqa: F401
from edgestream.models.event.source import Source, SourceParameter  # noqa: F401
from edgestream.models.event.destination import Destination, DestinationParameter, DestinationRoute  # noqa: F401

# noqa: F401# a: F401
from edgestream.models.network.vpn_client import VPNConfig  # noqa: F401
from edgestream.models.system.backup import Backup  # noqa: F401
from edgestream.models.system.audit import AuditEvent  # noqa: F401
