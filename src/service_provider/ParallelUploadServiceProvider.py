import time
from threading import Thread
from abc import abstractmethod
from queue import Queue

from src.service_provider.AbstractServiceProvider import AbstractServiceProvider

class ParallelUploadServiceProvider(AbstractServiceProvider):
    def __init__(self, uploadTool, config):
        super(ParallelUploadServiceProvider, self).__init__(uploadTool, config)
        self.uploadTaskTotal: int = 0
        self.uploadTaskStartAt: float = 0.0
        self.uploadInboundQueue: Queue = Queue()
        self.uploadOutboundQueue: Queue = Queue()

    def startParallelUploadWork(self, threads: int = 16):
        """执行并行上传"""
        self.uploadTaskStartAt = time.time()
        self.uploadTaskTotal = self.uploadInboundQueue.qsize()
        for i in range(threads):
            Thread(target=self.uploadWorkerThreadLoop, args=(), daemon=True).start()
        self.printProgress(0)
        while self.uploadOutboundQueue.qsize() < self.uploadTaskTotal:
            self.printProgress(self.uploadOutboundQueue.qsize())
        self.printProgress(self.uploadTaskTotal)
        print("\n请等待最后一个文件上传结束...")
        self.uploadInboundQueue.join()
        print("并行上传完成")
        # self.uploadOutboundQueue.join()

    def uploadWorkerThreadLoop(self):
        while True:
            task = self.uploadInboundQueue.get()
            result = self.uploadWorker(task)
            self.uploadOutboundQueue.put(result)
            self.uploadInboundQueue.task_done()

    @abstractmethod
    def uploadWorker(self, task):
        """并行上传的工作线程函数，必须通过队列传递参数"""
        pass

    def printProgress(self, finished: int):
        """输出多线程工作进度"""
        duration = int(time.time() - self.uploadTaskStartAt)
        seconds = duration % 60
        minutes = duration // 60
        total = self.uploadTaskTotal
        pct = finished / total
        bar = f"[{'=' * int(pct * 20 - 1) + '>':<20}]"
        spaces = " " * (len(str(total)) * 2)
        if (total - finished) <= 16:
            spaces = "没有卡住，马上就好" + spaces
        print(f"正在多线程上传：{finished}/{total} {bar} {pct:.1%} {minutes}:{seconds:02d}", spaces, end="\r", flush=True)
