class FlashMessage(object):
    def __init__(self,key=None,data=None,message=None):
        if message is not None:
            self.key,self.data = self._parse_message(message)
        else:
            self.key = key
            self.data = data

    def _parse_message(self,message):
        id,msg = message.split(':')
        try:
            key = int(id)
        except:
            raise NotImplementedError
        if key == 1 and msg!='':
            raise NotImplementedError
        else:
            if key == 1 or key == 3:
                data =[]
            elif key == 2:
                data = msg.split(';')
        return (key,data)

    def __str__(self):
        return str(self.key)+':'+';'.join([str(it) for it in self.data])
