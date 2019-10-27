import json
from .Job import Job
import os

class Jobs:

    def __init__(self, jobsFilePath):
        self.jobsFilePath = jobsFilePath
        self.jobs = {}
        self.initJobs()

    def initJobs(self):
        if not os.path.exists(self.jobsFilePath):
            self.saveJobs()
        else:
            with open(self.jobsFilePath) as jsonFile:
                try:
                    jobsProps = json.load(jsonFile)
                    self.jobsPropsToJobs(jobsProps)
                    self.saveJobs()
                except:
                    self.saveJobs()

    def jobsPropsToJobs(self, jobsProps):
        for id, props in jobsProps.items():
            self.jobs.update({id: Job(props=props)})

    def saveJobs(self):
        print(self.jobs)
        with open(self.jobsFilePath, 'w') as outfile:
            jobsProps = {}
            for id, job in self.jobs.items():
                jobsProps.update({id: job.props})
            json.dump(jobsProps, outfile, indent=1)

    def updateJob(self, id, job):
        self.jobs.update({id: job})
        self.saveJobs()

    def addJob(self, job):
        id = self.generateID()
        self.jobs.update({id: job})
        self.saveJobs()
        return id

    def removeJob(self, id):
        self.jobs.pop(id)

    def generateID(self):
        keys = self.jobs.keys()
        id = 0
        while id < 5000:
            if str(id) not in keys:
                break
            id += 1
        return str(id)
