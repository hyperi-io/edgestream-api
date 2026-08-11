# edgestream/crud/__init__.py

# Core logic
from .system.user import user
from .system.certificate_store import certificate
from .system.system import system
from .system.advanced_settings import advanced_setting
from .system.task_status import task
from .system.log_viewer import log_viewer
from .system.backups import backup

# Networking domain
from .network.ntp import ntp
from .network.dns import dns
from .network.static_route import static_route
from .network.static_host import static_host
from .network.dns_forwarder import dns_forwarder
from .network.ip_management import ip_mgmt

# VPN domain
from .network.vpn_client import vpnclient

# Event / Routing domain
from .event.source import source
from .event.source_params import source_parameter
from .event.destination import destination
from .event.destination_params import destination_parameter
from .event.destination_routes import destination_route
from .event.transform import transform
from .event.syslog import syslog