import numpy
import pandas

import sys
import time

def sort_branch_ids(df):
    swap_columns = df.columns[df.columns.str.startswith('branch_id')].tolist()
    if len(swap_columns)>1:
        swap_values = df.loc[:,swap_columns].values
        swap_values.sort(axis=1)
        df.loc[:,swap_columns] = swap_values
    if 'site' in df.columns:
        swap_columns.append('site')
    df = df.sort_values(by=swap_columns)
    for cn in swap_columns:
        df[cn] = df[cn].astype(int)
    return df

def sort_cb(cb):
    start = time.time()
    is_omega = cb.columns.str.contains('^omegaC')
    is_d = cb.columns.str.contains('^d[NS]C')
    is_nocalib = cb.columns.str.contains('_nocalib$')
    num_branch_id_cols = cb.columns.str.contains('^branch_id_').sum()
    col_order = []
    col_order += [ 'branch_id_'+str(i+1) for i in numpy.arange(num_branch_id_cols) ] # https://github.com/kfuku52/csubst/issues/20
    col_order += cb.columns[cb.columns.str.contains('^dist_')].sort_values().tolist()
    col_order += cb.columns[cb.columns.str.contains('^branch_num_')].sort_values().tolist()
    col_order += cb.columns[cb.columns.str.contains('^is_')].sort_values().tolist()
    col_order += cb.columns[(is_omega)&(~is_nocalib)].sort_values().tolist()
    col_order += cb.columns[(is_d)&(~is_nocalib)].sort_values().tolist()
    col_order += cb.columns[cb.columns.str.contains('^OC[NS]CoD$')].sort_values().tolist()
    col_order += cb.columns[cb.columns.str.contains('^OC[NS]_linreg_residual$')].sort_values().tolist()
    col_order += cb.columns[cb.columns.str.contains('^[NS]_sub_')].sort_values().tolist()
    col_order += cb.columns[cb.columns.str.contains('^OC[NS][any|dif|spe]')].sort_values().tolist()
    col_order += cb.columns[cb.columns.str.contains('^EC[NS][any|dif|spe]')].sort_values().tolist()
    col_order += cb.columns[(is_omega)&(is_nocalib)].sort_values().tolist()
    col_order += cb.columns[(is_d)&(is_nocalib)].sort_values().tolist()
    if (len(col_order) < cb.columns.shape[0]):
        col_order += [ col for col in cb.columns if col not in col_order ]
    cb = cb.loc[:,col_order]
    print('Time elapsed for sorting cb table: {:,} sec'.format(int(time.time() - start)))
    return cb

def sort_cb_stats(cb_stats):
    col_order = ['arity', 'elapsed_sec', 'cutoff_stat', 'fg_enrichment_factor', 'mode', 'dSC_calibration', ]
    col_order += cb_stats.columns[cb_stats.columns.str.contains('^num_')].tolist()
    if (len(col_order) < cb_stats.columns.shape[0]):
        col_order += [ col for col in cb_stats.columns if col not in col_order ]
    cb_stats = cb_stats.loc[:,col_order]
    return cb_stats

def merge_tables(df1, df2):
    start = time.time()
    columns = []
    columns = columns + df1.columns[df1.columns.str.startswith('branch_name')].tolist()
    columns = columns + df1.columns[df1.columns.str.startswith('branch_id')].tolist()
    columns = columns + df1.columns[df1.columns.str.startswith('site')].tolist()
    df = pandas.merge(df1, df2, on=columns)
    df = sort_branch_ids(df=df)
    print('Time elapsed for merging tables: {:,} sec'.format(int(time.time() - start)))
    return df

def set_substitution_dtype(df):
    col_exts = ['_sub', '2any', '2spe']
    sub_cols = list()
    for ck in col_exts:
        sub_cols = sub_cols + df.columns[df.columns.str.endswith(ck)].tolist()
    for sc in sub_cols:
        if (df[sc]%1).sum()==0:
            df.loc[:,sc] = df[sc].astype(int)
    return df

def get_linear_regression(cb):
    start = time.time()
    for prefix in ['OCS','OCN']:
        x = cb.loc[:,prefix+'any2any'].values
        y = cb.loc[:,prefix+'any2spe'].values
        x = x[:,numpy.newaxis]
        coef,residuals,rank,s = numpy.linalg.lstsq(x, y, rcond=None)
        cb.loc[:,prefix+'_linreg_residual'] = y - (x[:,0]*coef[0])
    print('Time elapsed for the linear regression of C ~ D: {:,} sec'.format(int(time.time() - start)))
    return cb

def chisq_test(x, total_S, total_N):
    obs = x.loc[['OCSany2spe','OCNany2spe']].values
    if obs.sum()==0:
        return 1
    else:
        contingency_table = numpy.array([obs, [total_S, total_N]])
        out = chi2_contingency(contingency_table, lambda_="log-likelihood")
        return out[1]

def get_cutoff_stat_bool_array(cb, cutoff_stat_str):
    is_enough_stat = True
    cutoff_stat_list = cutoff_stat_str.split('|')
    for cutoff_stat in cutoff_stat_list:
        cutoff_stat_list2 = cutoff_stat.split(',')
        cutoff_stat_exp = cutoff_stat_list2[0]
        cutoff_stat_value = float(cutoff_stat_list2[1])
        is_col = cb.columns.str.fullmatch(cutoff_stat_exp, na=False)
        if is_col.sum()==0:
            txt = 'The column "{}" was not found in the cb table. '
            txt += 'Check the format of the --cutoff_stat specification ("{}") carefully. Exiting.\n'
            sys.stderr.write(txt.format(cutoff_stat_exp, cutoff_stat_str))
            sys.exit(1)
        cutoff_stat_cols = cb.columns[is_col]
        for cutoff_stat_col in cutoff_stat_cols:
            is_enough_stat &= (cb.loc[:,cutoff_stat_col] >= cutoff_stat_value).fillna(False)
    return is_enough_stat