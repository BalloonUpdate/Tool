import sys

from src.object_storage_service.aliyun import AliyunOSS
from src.object_storage_service.tencent import TencentCOS

inDevelopment = not getattr(sys, 'frozen', False)

serviceProviders = {
    'tencent': TencentCOS,
    'aliyun': AliyunOSS
}
