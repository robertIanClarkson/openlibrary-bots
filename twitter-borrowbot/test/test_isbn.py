#!/usr/bin/python
import requests
import json
import sys

class ISBN_Tester:
  def read_isbn(self, filename):
    isbn_list = []
    f = open(filename, "r")
    for line in f:
      isbn_list.append(line.strip())
    return isbn_list

  def check_isbn(self, isbn):
    def is_json(str):
      try:
        json_object = str.json()
      except ValueError as e:
        return False
      return True

    print('(*) checking:', isbn)
    
    # get type
    if len(isbn) == 13:
      print('\t(+) is ISBN-13')
    elif len(isbn) == 10:
      print('\t(+) is ISBN-10')
    else:
      print('\t(x) is ISBN-', len(isbn))

    # ask archive
    resp = requests.get("http://openlibrary.org/isbn/"+isbn+".json")
    
    # get status code
    print("\t(+) response:", resp.status_code)

    # get format
    print("\t(+) is json:", is_json(resp))

    if(not is_json(resp) and len(isbn) == 13):
      print("\t(!) trying isbn-10 conversion")

    

      

# resp = requests.get("http://openlibrary.org/isbn/" + isbn + ".json")

if __name__ == "__main__":
  
  tester = ISBN_Tester()
  
  # get isbn from file
  if(len(sys.argv) > 1):
    for arg in sys.argv[1:]:
      isbn_list = tester.read_isbn(arg)
  else:
    isbn_list = tester.read_isbn("test.txt") 

  # check each ISBN
  for isbn in isbn_list:
    tester.check_isbn(isbn)


