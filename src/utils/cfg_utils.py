from yacs.config import CfgNode

def merge_cfgs(our_cfg, dt2_cfg):
    '''
    Enhances the default detectron2 config with the model 
    parameters defined in our config

    Args:
        our_cfg(AttrDict): experiment's config file
        dt2_cfg(CfgNode): config object as returned by detectron2.config.get_cfg()

    Returns:
        CfgNode: enhances config
    '''

    dt2_cfg.MODEL.ANCHOR_GENERATOR.SIZES = our_cfg.ANCHOR_SIZES
    dt2_cfg.SOLVER.BASE_LR = our_cfg.BASE_LR
    dt2_cfg.SOLVER.IMS_PER_BATCH = our_cfg.IMS_PER_BATCH
    dt2_cfg.SOLVER.MAX_ITER = our_cfg.MAX_ITER
    dt2_cfg.SOLVER.MOMENTUM = our_cfg.MOMENTUM
    dt2_cfg.SOLVER.WEIGHT_DECAY = our_cfg.WEIGHT_DECAY
    dt2_cfg.TEST.INTERVAL = our_cfg.EVAL_ITER
    dt2_cfg.INPUT.DO_STRONG_AUGMENTATION = our_cfg.DO_STRONG_AUGMENTATION
    dt2_cfg.INPUT.STRONG_AUGMENTATION = CfgNode(our_cfg.AUGMENTATIONS)

    return dt2_cfg