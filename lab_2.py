def forward_kinematics(self, theta1, theta2, theta3):
        def rotation_x(angle):
            # rotation about the x-axis implemented for you
            return np.array([
                [1, 0, 0, 0],
                [0, np.cos(angle), -np.sin(angle), 0],
                [0, np.sin(angle), np.cos(angle), 0],
                [0, 0, 0, 1]
            ])
        def rotation_y(angle):
            ## TODO: Implement the rotation matrix about the y-axis
            # return np.array([
            # ])
            return np.array([
                [np.cos(angle), 0, np.sin(angle), 0],
                [0, 1, 0, 0],
                [-np.sin(angle), 0, np.cos(angle), 0],
                [0, 0, 0, 1]
            ])
        
        def rotation_z(angle):
            ## TODO: Implement the rotation matrix about the z-axis
            # return np.array([
            # ])
            return np.array([
                [np.cos(angle), -np.sin(angle), 0, 0],
                [np.sin(angle), np.cos(angle), 0, 0],
                [0, 0, 1, 0],
                [0, 0, 0, 1]
            ])
        def translation(x, y, z):
            ## TODO: Implement the translation matrix
            # return np.array([
            # ])
            return np.array([
                [1, 0, 0, x],
                [0, 1, 0, y],
                [0, 0, 1, z],
                [0, 0, 0, 1]
            ])
        # T_0_1 (base_link to leg_front_r_1)
        # Translate 0.07500 along the x-axis
        # Translate -0.0445 along the y-axis
        # Rotate 90 degrees (np.pi/2 radians) around the y-axis (clockwise rotation)
        # Orient motor in direction theta1
        T_0_1 = translation(0.07500, -0.0445, 0) @ rotation_x(1.57080) @ rotation_z(theta1)
        # T_1_2 (leg_front_r_1 to leg_front_r_2)
        ## TODO: Implement the transformation matrix from leg_front_r_1 to leg_front_r_2
        # Translate 0.039 along the z-axis
        # Rotate 90 degrees (np.pi/2 radians) around the y-axis (clockwise rotation)
        # Orient motor in direction theta2
        T_1_2 = translation(0, 0, 0.039) @ rotation_y(-1.57080) @ rotation_z(theta2 - theta1)
        # T_2_3 (leg_front_r_2 to leg_front_r_3)
        ## TODO: Implement the transformation matrix from leg_front_r_2 to leg_front_r_3
        # Translate -0.0494 along the y-axis
        # Translate 0.0685 along the z-axis
        # Rotate -90 degrees (-np.pi/2 radians) around the y-axis (counter-clockwise rotation)
        # Orient motor in direction theta3
        T_2_3 = translation(0, -0.0494, 0.0685) @ rotation_y(1.57080) @ rotation_z(theta3 - theta2)
        # T_3_ee (leg_front_r_3 to end-effector)
        # Rotate 90 degrees around the y-axis (clockwise)
        T_3_ee = translation(0.06231, -0.06216, 0.018)
        # TODO: Compute the final transformation. T_0_ee is a concatenation of the previous transformation matrices
        T_0_ee = T_0_1 @ T_1_2 @ T_2_3 @ T_3_ee
        # TODO: Extract the end-effector position. The end effector position is a 3x3 matrix (not in homogenous coordinates)
        x_l = np.array([0],
                       [0],
                       [0],
                       [1])
        end_effector_position = T_0_ee @ x_l
        end_effector_position = end_effector_position[:3].flatten()
        return end_effector_position
