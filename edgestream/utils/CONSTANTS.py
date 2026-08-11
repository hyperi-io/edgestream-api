class Constants:
    INTERFACE_ORDERED_COLUMNS = [
        "name",
        "type",
        "ip_address",
        "netmask",
        "gateway",
        "nameserver1",
        "nameserver2",
        "nameserver3",
    ]
    CERTIFICATE_ORDERED_COLUMNS = [
        "id",
        "filename",
        "type",
        "size",
        "data",
        "created",
        "modified",
    ]
    SYSLOG_ORDERED_COLUMNS = ["port", "label", "protocol"]

    SA_INSTANCE_COLUMN = "_sa_instance_state"
    SERVICE_PARENT_TYPE = [
        "http",
        "kafka",
        "aws_s3",
        "vector",
        "file",
        "splunk_hec_logs",
        "elasticsearch_sink",
        "clickhouse",
    ]
    SINK_MAP = [
        ("http", "http_settings_list"),
        ("kafka", "kafka_settings_list"),
        ("aws_s3", "aws_settings_list"),
        ("vector", "vector_settings_list"),
        ("file", "file_settings_list"),
        ("elasticsearch_sink", "elasticsearch_settings_list"),
        ("clickhouse", "clickhouse_settings_list"),
    ]

    VPN_CONSOLE_MAPPING = [
        ("console_forward", "forward"),
        ("console_remote_address", "remote_address"),
        ("console_remote_port", "remote_port"),
        ("console_listen_address", "listen_address"),
        ("console_listen_port", "listen_port"),
    ]
