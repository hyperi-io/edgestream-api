from fastapi import APIRouter

from edgestream.api.v1.endpoints import (certificate_store, backup_restore, user,
                                         interface_management, vpn_client, advanced_setting,
                                         log_viewer, task_status, event_destination, event_syslog,
                                         event_transform, update, event_source, system_settings,
                                         networking_dns_client, networking_static_host,
                                         networking_ntp_client, networking_dns_forwarding,
                                         networking_static_route,
                                         system, authentication, event_routing,
                                         influx_config, system_services, wec_subscriptions)

api_router = APIRouter()

api_router.include_router(authentication.router, prefix="/auth", tags=["auth"])
api_router.include_router(influx_config.router, prefix="/influx_config", tags=["influx_config"])
api_router.include_router(
    user.router, prefix="/user", tags=["user"]
)
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(system_settings.router, prefix="/system_settings", tags=["system_settings"])
api_router.include_router(networking_dns_client.router, prefix="/dns_client", tags=["dns_client"])
api_router.include_router(networking_static_host.router, prefix="/static_host", tags=["static_host"])
api_router.include_router(networking_ntp_client.router, prefix="/ntp_client", tags=["ntp_client"])
api_router.include_router(networking_dns_forwarding.router, prefix="/dns_forwarding", tags=["dns_forwarding"])
api_router.include_router(networking_static_route.router, prefix="/static_route", tags=["static_route"])
api_router.include_router(interface_management.router, prefix="/interface_management", tags=["interface_management"])
api_router.include_router(interface_management.router, prefix="/interface_management", tags=["interface_management"])
api_router.include_router(interface_management.router, prefix="/interface_management", tags=["interface_management"])
api_router.include_router(event_syslog.router, prefix="/event_syslog", tags=["event_syslog"])
api_router.include_router(event_source.router, prefix="/event_source", tags=["event_source"])
api_router.include_router(event_transform.router, prefix="/event_transform", tags=["event_transform"])
api_router.include_router(event_destination.router, prefix="/event_destination", tags=["event_destination"])
api_router.include_router(certificate_store.router, prefix="/certificate_store", tags=["certificate_store"])
api_router.include_router(backup_restore.router, prefix="/backup_restore", tags=["backup_restore"])
api_router.include_router(event_routing.router, prefix="/event_routing", tags=["event_routing"])
api_router.include_router(vpn_client.router, prefix="/vpn_client", tags=["vpn_client"])
api_router.include_router(update.router, prefix="/update", tags=["update"])
api_router.include_router(advanced_setting.router, prefix="/advanced_setting", tags=["advanced_setting"])
api_router.include_router(log_viewer.router, prefix="/log_viewer", tags=["log_viewer"])
api_router.include_router(task_status.router, prefix="/task_status", tags=["task_status"])
api_router.include_router(system_services.router, prefix="/system_services", tags=["system_services"])
api_router.include_router(wec_subscriptions.router, prefix="/wec_subscriptions", tags=["wec_subscriptions"])
