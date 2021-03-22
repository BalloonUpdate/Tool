import sys

from src.service_provider.aliyun import AliyunOSS
from src.service_provider.ftp import Ftp
from src.service_provider.tencent import TencentCOS

inDevelopment = not getattr(sys, 'frozen', False)

serviceProviders = {
    'tencent': TencentCOS,
    'aliyun': AliyunOSS,
    'ftp': Ftp
}
