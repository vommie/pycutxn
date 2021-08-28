from .Job import Job

import json
import os
import copy
import os
from shutil import copyfile, move

class Jobs:

    # Initialization

    def __init__(self, jobsFilePath):
        self.jobsFilePath = jobsFilePath
        self.jobsFileBakPath = '%s._tmp' % jobsFilePath
        self.jobs = {}
        self.currentJob = False
        self.initJobs()

    def initJobs(self):
        try:
            if not os.path.exists(self.jobsFilePath):
                self.saveJobs()
            else:
                with open(self.jobsFilePath) as jsonFile:
                    try:
                        jobsProps = json.load(jsonFile)
                        self.jobsPropsToJobs(jobsProps)
                    except:
                        self.saveJobs()
        except Exception as e:
            raise Exception('Cannot initialize Jobs. Message:\n%s' % e)

    # Current job

    def newCurrentJob(self, videoFilePath=False, job=False):
        if videoFilePath and not job:
            job = Job('default', srcFilePath=videoFilePath)
        elif not videoFilePath and job: # Load job as new current session
            job = copy.deepcopy(job)
            job.setLog(False)
        else:
            print('Critical Error: Cannot create new job as parameters have conflict or are all not set.')
            exit(1)
        job.bindToProps(self.onJobPropsUpdated)
        self.jobs.update({'default': job})

    def onJobPropsUpdated(self, id, props):
        try:
            job = self.getJob(id)
            self.updateJob(id, job)
        except Exception as e:
            raise Exception(e)

    def getCurrentJob(self):
        return self.getJob('default')

    def saveCurrentJob(self):
        try:
            defaultJob = self.getCurrentJob()
            id = self.generateID()
            job = copy.deepcopy(defaultJob)
            job.setID(id)
            job.clearPropObservers()
            job.setState(0)
            job.bindToProps(self.onJobPropsUpdated)
            self.updateJob(id, job)
            return id, job
        except Exception as e:
            raise Exception(e)

    # Jobs management

    def getJob(self, id):
        return self.jobs.get(id)

    def updateJob(self, id, job):
        try:
            self.jobs.update({id: job})
            self.saveJobs()
        except Exception as e:
            raise Exception('Cannot update Job. Message:\n%s' % e)

    def removeJob(self, id):
        try:
            self.deleteDeshakeFile(id)
            self.jobs.pop(id)
            return self.saveJobs()
        except Exception as e:
            raise Exception('Cannot remove Job. Message:\n%s' % e)

    def saveJobs(self):
        '''Saves the jobs to the jobs.json file

        :return: True on success, False if something went wrong
        '''
        fileEditPath = self.jobsFilePath
        if os.path.isfile(self.jobsFilePath):
            copyfile(self.jobsFilePath, self.jobsFileBakPath)
            fileEditPath = self.jobsFileBakPath
        try:
            with open(fileEditPath, 'w') as outfile:
                jobsProps = {}
                for id, job in self.jobs.items():
                    jobsProps.update({id: job.getProps()})
                json.dump(jobsProps, outfile, indent=1)
        except Exception as e:
            if os.path.isfile(self.jobsFileBakPath): os.remove(self.jobsFileBakPath)
            raise Exception('Error: Cannot save jobs to file. This will lead to an inconsistency between jobs in the current session in the GUI and the saved jobs. Message:\n%s' % e)
        finally:
            if os.path.isfile(self.jobsFileBakPath): move(self.jobsFileBakPath, self.jobsFilePath)

    # Other functions

    def generateID(self):
        keys = self.jobs.keys()
        id = 0
        while id < 5000:
            if str(id) not in keys:
                break
            id += 1
        return str(id)

    def jobsPropsToJobs(self, jobsProps):
        # Create the default job
        try:
            defJob = Job('default', props=jobsProps.get('default'))
            jobsProps.pop('default', None)
            defJob.bindToProps(self.onJobPropsUpdated)
            self.updateJob('default', defJob)
        except Exception as e:
            raise Exception(e)
        # Create jobs and check their position for duplicates
        jobs = {}
        jobsDups = {}
        positionDup = 0
        for id, props in jobsProps.items():
            job = Job(id, props=props)
            position = job.getPosition()
            try:
                jobs[position]
                while 1:
                    try:
                        jobsDups[positionDup]
                        positionDup += 1
                    except:
                        jobsDups.update({positionDup: job})
                        break

            except:
                jobs.update({position: job})
        # Sort positions (remove gaps and append duplicates)
        position = 0
        try:
            for key in sorted(jobs.keys()):
                job = jobs[key]
                job.setPosition(position)
                position += 1
                job.bindToProps(self.onJobPropsUpdated)
                self.updateJob(job.getID(), job)
            for key in sorted(jobsDups.keys()):
                job = jobsDups[key]
                job.setPosition(position)
                position += 1
                job.bindToProps(self.onJobPropsUpdated)
                self.updateJob(job.getID(), job)
        except Exception as e:
            raise Exception(e)

    def deleteDeshakeFile(self, id):
        '''Deletes the deshake file from the config dir for a job'''
        job = self.getJob(id)
        deshakeFile = job.getFilterDeshakeFile()
        if not deshakeFile or not os.path.isfile(deshakeFile): return
        os.remove(deshakeFile)
