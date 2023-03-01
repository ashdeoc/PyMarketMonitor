import json
import threading
import pandas as pd
import time
import csv
import urllib.request
from prompt_toolkit.application import Application
from prompt_toolkit import PromptSession
from prompt_toolkit.document import Document
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, VSplit, Window
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.styles import Style 
from prompt_toolkit.widgets import TextArea, SearchToolbar
from prompt_toolkit.layout import FormattedTextControl, WindowAlign,  BufferControl
from prompt_toolkit.cursor_shapes import CursorShape
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding.bindings.focus import focus_next, focus_previous
from prompt_toolkit.key_binding.bindings.page_navigation import scroll_page_up, scroll_page_down
from concurrent.futures import ThreadPoolExecutor
#-------------------------------------------------------------

class YahooClient(object):
    ''' Class to manage Yahoo finance data requests'''
    def __init__(self):
       self._yfin_link = "https://query2.finance.yahoo.com/v7/finance/quote?symbols="

    def _yfin_query_one(self, symbol):
        ''' obtains information of a single security'''
        if symbol == None:
            return {}
        else:
            urlData = self._yfin_link+symbol
           # urlData = "https://query2.finance.yahoo.com/v10/finance/quoteSummary/{}".format(stock)
            user_agent = 'Mozilla/5.0'
            headers = {'User-Agent': user_agent}
            webUrl = urllib.request.urlopen(urlData)
            if (webUrl.getcode() == 200):
                data = webUrl.read()
                data = (data.decode('ascii'))
                yFinJSON = json.loads(json.loads(json.dumps(data).replace('{}', 'null')))
                return  yFinJSON["quoteResponse"]["result"][0]
            else:
                return None

    def multi_thread_parse(self, ticker):
        """gets next url in queue and calls scrape_yahoo_finance() until queue is empty"""
        with ThreadPoolExecutor() as executor:
            return executor.map(self._yfin_query_one, ticker)


    def Watchlist_df(self, tickers):
        ''' Collates the asset data fields into a formated pandas dataframe '''
        fields = {  'regularMarketPrice':'Price','regularMarketChangePercent': '1D%', 'currency':'Curr',
                   'typeDisp':'Type', 'shortName':'Name', 'marketCap':'MCapBn','exchange':'Exch', 'priceToBook':'P/B',
                   'trailingPE':'ltm P/E', 'forwardPE':'fwd P/E','marketState':'State'}
        results = {}
        for ticker in tickers:
            tickerData = self._yfin_query_one(ticker)
            singleResult = {}
            if not tickerData.__contains__('"result":[]'):
                for key in fields.keys():
                    if key in tickerData:
                        singleResult[fields[key]] = tickerData[key]
                    else:
                        singleResult[fields[key]] = "N/A"
            else:
                pass
            results[ticker] = singleResult
        #default is keys are columns
        dfTransp = pd.DataFrame.from_dict(results)
        #unless you set orient as index
        df = pd.DataFrame.from_dict(results, orient='index')
        df_formated = df.applymap(lambda x: round(x, 1) if isinstance(x, (int, float)) else x)
        df_formated['Price'] = pd.Series([round(val, 3) for val in df['Price']], index = df.index)
        df_formated['1D%'] = pd.Series([round(val, 2) for val in df['1D%']], index = df.index)
        df_formated['Type'] = df_formated['Type'].str[:4]
        df_formated['Name'] = df_formated['Name'].str[:10]
        df_formated['MCapBn'] = (pd.to_numeric(df_formated['MCapBn'], errors='coerce')/1000000000).round(2)
        # df_formated['MkCap'] = df_formated['MkCap'].astype(str).apply(lambda x: x.replace('.0',''))
        # df['Var3'] = pd.Series(["{0:.2f}%".format(val * 100) for val in df['var3']], index = df.index)
        return str(df_formated)


class Watchlist_Loader(object):
    ''' Populate a list of saved ticker symbols from a csv file '''
    def __init__(self):
       self._default_loadfile = 'default_ticker_list.csv'
       self._symbols = []
       self._file_name = ''

    def get_symbols_from_csv(self, _file_name):
        with open(_file_name, newline='') as inputfile:
            for row in csv.reader(inputfile):
                self._symbols.append(row[0])
        return self._symbols

    def load_defaultcsv_symbols(self):
        symb = self.get_symbols_from_csv('default_ticker_list.csv')
        return symb

    
class WatchList_Area(object):
    def __init__(self):
         self.__watchlist_title_view_text = 'Watchlist'
         self._mainbuffer = MAIN_BUFFER

    def get_watchlist_stocks_view(self):
        return Window(BufferControl(buffer=self._mainbuffer,focusable=True,focus_on_click=True),)

        
class CommandInput_Area(object):
    def __init__(self):
        self._completer = 'to_do'

    def get_input_instructions_view(self):
        return TextArea(height=1,
                        prompt='>',
                        style="class:input-field",
                        complete_while_typing=True,
                        multiline=False,
                        wrap_lines=False,
                        # completer=path_completer,
                        )
     

class PyTickerLayout(object):
    def __init__(self):
        self.__watchlist = WatchList_Area()
        self.__commandinput = CommandInput_Area()
        
    def _get_main_content_layout(self):        
        return self.__watchlist.get_watchlist_stocks_view()

    def get_layout(self) -> Layout:
        root_container = HSplit([self.__commandinput.get_input_instructions_view(),
            self._get_main_content_layout(),
            ], padding_char='-', padding=1) #'#242525'
        return Layout(container=root_container)
        

class PyTickerApplication(object):
    '''Creating an Application instance'''
    def __init__(self):
        self._application = None
        self._pyticker_layout = PyTickerLayout()
        self._yf = YahooClient()
        self._refresh_rate_seconds = 30 
        
    def init_application(self):
        terminal_title = "PyMarketWatch"
        print(f'\33]0;{terminal_title}\a', end='', flush=True)
        layout = self._pyticker_layout.get_layout()
        self._application = Application(layout=layout, full_screen=True, key_bindings=bindings, cursor=CursorShape.UNDERLINE)

    def _invalidate(self):
        watchlist_text = self._yf.Watchlist_df(watchlist_symbols)
        MAIN_BUFFER.text = (watchlist_text)
        self._application.invalidate()

    def _do_every(self,delay, task):
        while True:
            task()
            time.sleep(delay)

    def run(self):
        watchlist_text = self._yf.Watchlist_df(watchlist_symbols)
        MAIN_BUFFER.text = watchlist_text
        threading.Thread(target=lambda: self._do_every(self._refresh_rate_seconds, self._invalidate), daemon=True).start()
        self._application.run()


MAIN_BUFFER = Buffer()
watchlist_symbols=[]
watchlist_symbols = Watchlist_Loader().load_defaultcsv_symbols()

bindings = KeyBindings()
bindings.add('s-tab')(focus_next)
@bindings.add('c-c')
def _(event):
    event.app.exit()
      
def main():
    ''' Starts main application loop '''
    pd.set_option('display.max_rows', None)
    pyticker = PyTickerApplication()
    pyticker.init_application()
    pyticker.run()
        
if __name__ == '__main__':
    main()

#-----------------------------------------------------------------



