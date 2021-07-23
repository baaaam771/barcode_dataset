#coding=utf-8
import json
import os
import time
import threading
import uuid
from shutil import copyfile
from barcode_reader import BarcodeReaderX

class Batch_session():
    def __init__(self, img_folder, output_folder, template=None,session_id=None):
        self.img_folder = img_folder
        self.output_folder = output_folder
        self.id = uuid.uuid1().hex
        
        if session_id != None:
            self.id = session_id
        self.json_folder = os.path.join(self.output_folder,self.id)
        if os.path.exists(self.json_folder) == False:
            os.mkdir(self.json_folder)
            
        f = open(os.path.join(self.json_folder,"img_folder"),"w")
        f.write(img_folder)
        f.close()
        
        self.reader = BarcodeReaderX()
        
        self.files_list = []
        self.processed = 0
        self.load_files_list()
        self.reading = True;
    
    def decode_and_save_results(self, engine=""):
        self.processed = 0
        for filename in self.files_list:
            print("Decoding "+filename)
            if self.reading == False:
                print("Stopped")
                return
            start_time = time.time()
            result_dict = {}
            results = []
            try:
                result_dict = self.reader.decode_file(os.path.join(self.img_folder,filename),engine=engine)
            except:
                print("Error")
            end_time = time.time()
            elapsedTime = int((end_time - start_time) * 1000)
            
            if "results" in result_dict:
                results = result_dict["results"]
            if "elapsedTime" in result_dict:
                elapsedTime = result_dict["elapsedTime"]
            
            json_dict = {}
            json_dict["elapsedTime"] = elapsedTime
            json_dict["results"] = results
            json_string = json.dumps(json_dict, indent="\t")
            
            f = open(os.path.join(self.json_folder,self.get_json_filename(filename, engine)),"w")
            f.write(json_string)
            f.close()
            self.processed=self.processed+1
            
    def start_reading(self, engine=""):
        self.reading = True
        self.reader.start_commandline_zmq_server_if_unstarted()
        threading.Thread(target=self.decode_and_save_results, args=(engine,)).start()
        
    def stop_reading(self):
        self.reader.stop_commandline_zmq_server_if_started()
        self.reading = False
            
    def load_files_list(self):
        for filename in os.listdir(self.img_folder):
            name, ext = os.path.splitext(filename)
            if ext.lower() in ('.png','.jpg','.jpeg','.bmp'):
                self.files_list.append(filename)

    def get_process(self):
        return "{}/{}".format(self.processed, len(self.files_list))
        
    def completed(self, engine=""):
        imgs_list = {}
        json_list = {}

        for filename in self.files_list:
            imgs_list[filename] = ""
            json_filename = self.get_json_filename(filename, engine)
            if os.path.exists(os.path.join(self.json_folder,json_filename)):
                json_list[json_filename] = ""
        for img_filename in imgs_list:
            if self.get_json_filename(img_filename,engine) not in json_list:
                return False
        return True
        
    '''
    Get json name based on image name.
    Image name: 1.jpg
    Json name: 1.jpg.json
    With engine: 1.jpg-engine.json
    '''
    def get_json_filename(self, filename, engine=""):
        if engine!="":
            return filename+"-"+engine+".json"
        else:
            return filename+".json"
    
    def get_ground_truth_list(self, filename):
        txt_path = os.path.join(self.img_folder,filename+".txt")
        if os.path.exists(txt_path):
            f = open(txt_path, "r")
            ground_truth_list=json.loads(f.read())
            f.close()
            return ground_truth_list
        return []
    
    def get_statistics(self, engine=""):
        data = {}
        img_results = {}
        total_elapsedTime = 0
        undetected = 0
        wrong_detected = 0
        
        for filename in self.files_list:
            json_filename = self.get_json_filename(filename, engine)
            json_path = os.path.join(self.json_folder,json_filename)
            if os.path.exists(json_path):
                failed = False
                f = open(json_path,"r",encoding="utf-8")
                image_decoding_result = json.loads(f.read())
                ground_truth_list = self.get_ground_truth_list(filename)
                img_results[filename] = image_decoding_result
                if "results" in image_decoding_result:
                    results=image_decoding_result["results"]
                    if len(results)==0:
                        undetected=undetected+1
                        failed = True
                    else:
                        barcode_text = ""
                        for result in results:
                            barcode_text = barcode_text + " " + result["barcodeText"]
                        total_elapsedTime=total_elapsedTime+int(image_decoding_result["elapsedTime"])
                        
                        for ground_truth in ground_truth_list:
                            if barcode_text.find(ground_truth) == -1:
                                wrong_detected=wrong_detected+1
                                image_decoding_result["wrong_detected"] = True
                                failed = True
                                exit
                else:
                    undetected=undetected+1
                    failed = True
                    
                image_decoding_result["ground_truth"] = ground_truth_list
                image_decoding_result["failed"] = failed
                if failed == True:
                    self.copy_undetected_to_failed_folder(filename,engine)
                
        total = len(self.files_list)
        correctly_detected = total - undetected - wrong_detected
        data["img_results"] = img_results
        data["total"] = total
        data["undetected"] = undetected
        data["wrong_detected"] = wrong_detected
        
        data["precision"] = correctly_detected / (total - undetected)
        data["accuracy"] = correctly_detected / total
        data["time_elapsed"] = total_elapsedTime
        data["average_time"] = total_elapsedTime / total
        return data
        
    def copy_undetected_to_failed_folder(self, filename, engine=""):
        img_path = os.path.join(self.img_folder,filename)
        if engine == "":
            failed_folder_path = os.path.join(self.json_folder,"failed")
        else:
            failed_folder_path = os.path.join(self.json_folder,"failed-" + engine)
        if os.path.exists(failed_folder_path) == False:
            os.mkdir(failed_folder_path)
        target = os.path.join(failed_folder_path,filename)
        copyfile(img_path,target)
        
        
if __name__ == '__main__':
    session = Batch_session("./","./tmp",session_id="c7edc4c5ea9011eb8965e84e068e29b8")
    if (session.completed()):
        print("Already completed")
        print(session.get_statistics())
    else:
        session.start_reading()
        while session.completed()==False:
            time.sleep(0.2)
            print(session.get_process())
        print("Completed")
    
        