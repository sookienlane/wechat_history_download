#!/usr/bin/env python3
import sqlite3
import subprocess
import logging
import os
import shutil
import hashlib
import jsonlines

from dotenv import load_dotenv
load_dotenv()


class DAO(object):
    def __init__(self, db_name, db_dir):
        self._db_name = db_name
        self._db = sqlite3.connect(os.path.join(db_dir, db_name))
        self._cursor = self._db.cursor()

    def __del__(self):
        self._cursor.close()

        self._db.commit()
        self._db.close()

    def get_cursor(self):
        return self._cursor


class WechatDB(object):
    def __init__(self):
        self.wechat_root = os.path.expanduser(os.getenv("WECHAT_ROOT"))
        self.wechat_raw_key = os.getenv("WECHAT_RAW_KEY")
        self.db_dir = 'wechat_history_export_plain_dbs'
        self.name = os.getenv("NAME")

    def prepare_db_dir(self):
        if os.path.exists(self.db_dir):
            logging.debug('removing existing db_dir "{}"'.format(self.db_dir))
            shutil.rmtree(self.db_dir)
        os.mkdir(self.db_dir)

    def copy_db_files(self):
        dirs = ['Message', 'Group', 'Contact']
        for d in dirs:
            for f in os.listdir(os.path.join(self.wechat_root, d)):
                if 'backup' in f or 'db' not in f:
                    continue
                shutil.copyfile(os.path.join(self.wechat_root, d, f), os.path.join(self.db_dir, f))
        logging.debug('copying encrypted database done')

    def remove_db_files(self):
        shutil.rmtree(self.db_dir)

    def get_merge_wal_and_decrypt_sql(self, db_name):
        db_name = db_name.split('.')[0]
        merge_wal_and_decrypt_sql_tpl = '''
    PRAGMA key = "x'{}'";
    PRAGMA cipher_page_size = 1024;
    PRAGMA kdf_iter = '64000';
    PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA1;
    PRAGMA cipher_hmac_algorithm = HMAC_SHA1;

    PRAGMA wal_checkpoint;

    ATTACH DATABASE '{}.db' AS plaintext KEY '';
    SELECT sqlcipher_export('plaintext');
    DETACH DATABASE plaintext;
    '''
        return merge_wal_and_decrypt_sql_tpl.format(self.wechat_raw_key, db_name + '_dec')

    def merge_wal_and_decrypt_all(self):
        def merge_wal_and_decrypt(db_name):
            sql = self.get_merge_wal_and_decrypt_sql(db_name)
            p = subprocess.run(['sqlcipher', db_name], stdout=subprocess.PIPE,
                               input=sql, cwd=self.db_dir, encoding='utf8')
            if p.returncode != 0:
                logging.exception(p.stdout)

        dbs = filter(lambda f: 'shm' not in f and 'wal' not in f, os.listdir(self.db_dir))
        logging.debug('begin to decrypt database to "{}" directory'.format(self.db_dir))
        for db in dbs:
            merge_wal_and_decrypt(db)
        logging.debug('decrypt database done')

    def get_chat_hash_by_remark(self, remark):
        db_name = 'wccontact_new2_dec.db'
        table_name = 'WCContact'
        filter_field = 'm_nsAliasName'

        contact = DAO(db_name, self.db_dir)
        sql = "select m_nsUsrName, nickname, m_nsRemark from {} where {}='{}'".format(table_name, filter_field, remark)
        contact.get_cursor().execute(sql)
        result = contact.get_cursor().fetchall()
        logging.debug('contact info: {}'.format(result))
        hl = hashlib.md5()

        for c in result:
            # 有人会在表里有两条记录，但是其中一条的m_nsUserName为空串
            if not c[0]:
                continue
            hl.update(c[0].encode(encoding='utf-8'))
            md5_sum = hl.hexdigest()
            logging.debug('chat hash of {} is: {}'.format(remark, md5_sum))
            return md5_sum

        logging.warning('find contact "{}" by remark failed'.format(remark))
        return None

    def get_dbname_and_tablename_contains_chat_hash(self, chat_hash):
        dbs = filter(lambda d: 'msg' in d and 'dec' in d, os.listdir(self.db_dir))
        for db_name in dbs:
            db = DAO(db_name, self.db_dir)
            db.get_cursor().execute('select name from sqlite_master where type="table" and name not like "sqlite_%"')
            tables = db.get_cursor().fetchall()
            for table in tables:
                table_name = table[0]
                this_hash = table_name.split('_')[1]
                if this_hash == chat_hash:
                    logging.debug('chat hash "{}" found: database: "{}", table: "{}"'
                                  .format(chat_hash, db_name, table_name))
                    return db_name, table_name
        return None, None

    def main(self,):
        self.prepare_db_dir()
        self.copy_db_files()
        self.merge_wal_and_decrypt_all()

        chat_hash = self.get_chat_hash_by_remark(self.name)
        if not chat_hash:
            return None
        else:
            db_name, table_name = self.get_dbname_and_tablename_contains_chat_hash(chat_hash)
            if not db_name or not table_name:
                return None
            else:
                contact = DAO(db_name, self.db_dir)
                sql = 'select * from {}'.format(table_name)
                contact.get_cursor().execute(sql)
                result = contact.get_cursor().fetchall()
                sql = "PRAGMA table_info({})".format(table_name)
                contact.get_cursor().execute(sql)
                columns = contact.get_cursor().fetchall()
                final = []
                for result_one in result:
                    final.append({
                        columns[i][1]: result_one[i] for i in range(1, 9)
                    })
        with jsonlines.open("history_{}.jsonl".format(self.name), "w") as f:
            for x in final:
                f.write(x)
        self.remove_db_files()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(filename)s: [%(levelname)s] %(message)s')

    wechatdb = WechatDB()
    wechatdb.main()

# 系统消息：1000
# 文本消息，包含小表情：1
# 图片消息，相机中的照片和配置有不同，从相册中发送的消息中会保留一个 MMAsset，如同 PAAset：3
# 位置消息： 48
# 语音消息：34
# 名片消息，公众号名片和普通名片用的是同一种类型：42
# 大表情：47
# 分享消息，这种消息会含有多种类型，比如分享的收藏，分享的小程序，微信红包等等。这种消息类型可以避免不断添加多种消息类型，像这种预先定义一种消息类型，预留一些字段，这样产品添加消息类型的时候，UI 可以任意组合：49
