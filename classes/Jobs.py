import json
from .Job import Job
import os
import copy

class Jobs:

    # Initialization

    def __init__(self, jobsFilePath):
        self.jobsFilePath = jobsFilePath
        self.jobs = {}
        self.currentJob = False
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

    # Other functions

    def newCurrentJob(self, videoFilePath):
        self.currentJob = Job(srcFilePath=videoFilePath)
        self.currentJob.bindToProps(self.jobUpdated)

    def jobUpdated(self, props):
        print('jobUpdated')
        self.saveJobs()

    def jobsPropsToJobs(self, jobsProps):
        for id, props in jobsProps.items():
            self.jobs.update({id: Job(props=props)})

    def saveJobs(self):
        with open(self.jobsFilePath, 'w') as outfile:
            jobsProps = {}
            for id, job in self.jobs.items():
                jobsProps.update({id: job.getProps()})
            json.dump(jobsProps, outfile, indent=1)

    def updateJob(self, id, job):
        self.jobs.update({id: job})
        self.saveJobs()

    def addJob(self, job):
        print('addJob')
        id = self.generateID()
        # self.jobs.update({id: copy.deepcopy(job)})
        self.jobs.update({id: job})
        self.saveJobs()
        return id

    def removeJob(self, id):
        self.jobs.pop(id)
        self.saveJobs()

    def generateID(self):
        keys = self.jobs.keys()
        id = 0
        while id < 5000:
            if str(id) not in keys:
                break
            id += 1
        return str(id)

    def getJob(self, id):
        return self.jobs.get(id)
